from . import coupon

import csv
import os
from datetime import datetime, timezone
from typing import cast
from sqlalchemy import func  # type: ignore
from sqlalchemy.orm import joinedload  # type: ignore
from flask import request, jsonify, g, current_app
from werkzeug.utils import secure_filename

from app.models.coupon import Coupon, COUPON_STATUS
from app.models.merchant import Merchant
from app.models.offer import Offer
from app.models.user_offer_usage import UserOfferUsage
from app.models.upload_job import UploadJob, UPLOAD_STATUS
from app import db
from app.utils import roles_required
from app.tasks.coupon_upload import process_coupon_upload


def _ensure_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validate_offer_for_upload(offer: Offer):
    now = datetime.now(timezone.utc)
    offer_end = _ensure_utc(offer.end_date)
    if offer_end <= now:
        return False
    return True


@coupon.route('/<id>/redeem', methods=['POST'])
@roles_required('merchant')
def redeem_coupon(id):
    """
    Redeem a coupon.
    Scenarios:
    - Redeem a valid coupon
    - Redeem an already redeemed coupon
    - Redeem a non-existent coupon
    """
    user = g.user
    if not user:
        return jsonify({"message": "Unauthorized"}), 401

    session = db.session
    now = datetime.now(timezone.utc)

    try:
        coupon: Coupon | None = session.query(
            Coupon).filter_by(id=id).with_for_update().first()
        if not coupon:
            session.rollback()
            return jsonify({"message": "Coupon not found or does not belong to the user"}), 404

        if coupon.offer.merchant_id != user.id:
            session.rollback()
            return jsonify({"message": "Coupon does not belong to this merchant"}), 403

        coupon_status = cast(str, coupon.status)

        if coupon_status == COUPON_STATUS["REDEEMED"]:
            session.rollback()
            return jsonify({"message": "Coupon already redeemed"}), 400
        if coupon_status == COUPON_STATUS["REVOKED"]:
            session.rollback()
            return jsonify({"message": "Coupon has been revoked"}), 400
        if coupon_status == COUPON_STATUS["EXPIRED"]:
            session.rollback()
            return jsonify({"message": "Coupon has expired"}), 400

        expiry_date = cast(datetime, coupon.expiry_date)
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        if expiry_date <= now:
            coupon.status = COUPON_STATUS["EXPIRED"]
            session.commit()
            return jsonify({"message": "Coupon has expired"}), 400

        offer_end = cast(datetime, coupon.offer.end_date)
        if offer_end.tzinfo is None:
            offer_end = offer_end.replace(tzinfo=timezone.utc)
        if coupon.offer.status in ['inactive', 'suspended']:
            session.rollback()
            return jsonify({"message": "Offer is not active"}), 400
        if coupon.offer.status == 'expired' or offer_end <= now:
            session.rollback()
            return jsonify({"message": "Offer has expired"}), 400

        total_redemptions = session.query(func.count(Coupon.id)).filter(
            Coupon.offer_id == coupon.offer_id,
            Coupon.status == COUPON_STATUS["REDEEMED"]
        ).scalar() or 0

        coupon.status = COUPON_STATUS["REDEEMED"]
        coupon.redeemed_at = now

        # Calculate savings amount based on offer details
        savings_amount = None
        if coupon.offer.discount_type == 'percentage':
            # For percentage discounts, we can't calculate exact savings without purchase amount
            # This would typically be provided in request data in a real scenario
            pass
        elif coupon.offer.discount_type == 'fixed_amount':
            savings_amount = coupon.offer.discount_value
        elif coupon.offer.discount_type == 'buy_one_get_one':
            # Estimate 50% of a typical purchase - would be better to get actual amount
            pass
        elif coupon.offer.discount_type == 'free_item':
            # Estimate value of free item - would be better to get actual amount
            pass

        # Update offer average redemption time
        redemption_time = (now - coupon.created_at).total_seconds() / 3600
        if coupon.offer.avg_redemption_time_hours:
            coupon.offer.avg_redemption_time_hours = (
                (coupon.offer.avg_redemption_time_hours *
                 total_redemptions) + redemption_time
            ) / (total_redemptions + 1)
        else:
            coupon.offer.avg_redemption_time_hours = redemption_time

        usage_record = session.query(UserOfferUsage).filter(
            UserOfferUsage.consumer_id == coupon.consumer_id,
            UserOfferUsage.offer_id == coupon.offer_id
        ).with_for_update().first()

        if not usage_record:
            usage_record = UserOfferUsage(
                consumer_id=coupon.consumer_id,
                offer_id=coupon.offer_id,
                usage_count=0,
                total_savings=0,
                total_redemptions=0
            )
            session.add(usage_record)
            session.flush()

        usage_record.record_redemption(savings_amount, commit=False)

        session.commit()

        return jsonify({
            "message": "Coupon redeemed successfully",
            "data": {
                'id': coupon.id,
                'couponCode': coupon.coupon_code,
                'offer': {
                    'id':  coupon.offer.id,
                    'title': coupon.offer.title,
                    'slug': coupon.offer.slug,
                    'coverImage': coupon.offer.cover_image,
                    'discountType': coupon.offer.discount_type,
                    'discountValue': coupon.offer.discount_value,
                    'currency': coupon.offer.currency,
                },
                'consumer': {
                    'id': coupon.consumer.id,
                    'name': coupon.consumer.first_name + ' ' + coupon.consumer.last_name,
                    'email': coupon.consumer.email.split('@')[0][:3] + '****@' + coupon.consumer.email.split('@')[1] if coupon.consumer.email else None,
                },
                'redeemedAt': coupon.redeemed_at if coupon.redeemed_at else None,
                'expiryDate': coupon.expiry_date if coupon.expiry_date else None,
                'status': coupon.status,
                'qrCode': coupon.qr_code if coupon.qr_code else None,
                'savings_amount': savings_amount,
                'usage_stats': {
                    'total_redemptions': usage_record.total_redemptions,
                    'total_savings': usage_record.total_savings,
                    'usage_count': usage_record.usage_count
                }
            }
        }), 200
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error redeeming coupon: {str(e)}")
        return jsonify({"message": "An error occurred while redeeming the coupon"}), 500


@coupon.route('/upload', methods=['POST'])
@roles_required('merchant')
def upload_coupons():
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"message": "Unauthorized"}), 401

    offer_id = request.form.get('offer_id')
    if not offer_id:
        return jsonify({"message": "Missing offer_id"}), 400

    offer: Offer | None = db.session.query(
        Offer).filter_by(id=offer_id).first()
    if not offer:
        return jsonify({"message": "Offer not found"}), 404

    if offer.merchant_id != merchant.id:
        return jsonify({"message": "Offer does not belong to this merchant"}), 403

    if not _validate_offer_for_upload(offer):
        return jsonify({"message": "Offer is expired"}), 400

    file = request.files.get('file')
    if not file or file.filename == '' or file.filename is None:
        return jsonify({"message": "Missing CSV file"}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({"message": "File must be a CSV"}), 400

    # Validate file size (<= 5MB)
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    max_size = current_app.config.get(
        "COUPON_UPLOAD_MAX_SIZE", 5 * 1024 * 1024)
    if size > max_size:
        return jsonify({"message": "File size exceeds 5MB"}), 400

    # Validate CSV headers
    header_line = file.stream.readline().decode('utf-8-sig')
    file.stream.seek(0)
    try:
        headers = next(csv.reader([header_line]))
    except Exception:
        headers = []

    normalized_headers = [h.strip().lower()
                          for h in headers] if headers else []
    if normalized_headers != ["coupon_code", "expiry_date"]:
        return jsonify({"message": "Invalid CSV headers"}), 400

    job = UploadJob(
        merchant_id=merchant.id,
        offer_id=offer.id,
        status=UPLOAD_STATUS["PENDING"],
        file_path=""
    )
    db.session.add(job)
    safe_name = secure_filename(file.filename)
    if not safe_name:
        return jsonify({"message": "Invalid filename"}), 400
    upload_dir = current_app.config.get("COUPON_UPLOAD_DIR")
    if not upload_dir:
        current_app.logger.error("COUPON_UPLOAD_DIR not configured")
        return jsonify({"message": "Server configuration error"}), 500
    file_path = os.path.join(upload_dir, f"{job.id}_{safe_name}")
    file.save(file_path)
    file_path = os.path.join(upload_dir, f"{job.id}_{safe_name}")
    try:
        file.save(file_path)
        job.file_path = file_path
        db.session.commit()
    except Exception:
        db.session.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    file.save(file_path)
    job.file_path = file_path
    db.session.commit()

    process_coupon_upload.delay(job.id)

    return jsonify({
        "message": "Upload accepted for processing",
        "data": {"job_id": job.id}
    }), 201


@coupon.route('/upload/<job_id>/status', methods=['GET'])
@roles_required('merchant')
def upload_status(job_id):
    merchant: Merchant = g.user
    job: UploadJob | None = db.session.query(UploadJob).filter_by(
        id=job_id, merchant_id=merchant.id
    ).first()

    if not job:
        return jsonify({"message": "Upload job not found"}), 404

    return jsonify({
        "data": {
            "id": job.id,
            "status": job.status,
            "offer_id": job.offer_id,
            "total_rows": job.total_rows,
            "processed_rows": job.processed_rows,
            "successful_rows": job.successful_rows,
            "failed_rows": job.failed_rows,
            "errors": job.errors or [],
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        }
    }), 200


@coupon.route('/upload/history', methods=['GET'])
@roles_required('merchant')
def upload_history():
    merchant: Merchant = g.user
    jobs = db.session.query(UploadJob).options(
        joinedload(UploadJob.offer)
    ).filter_by(
        merchant_id=merchant.id
    ).order_by(UploadJob.created_at.desc()).all()

    history = []
    for job in jobs:
        offer = job.offer
        history.append({
            "id": job.id,
            "status": job.status,
            "offer": {
                "id": offer.id if offer else job.offer_id,
                "title": offer.title if offer else None
            },
            "total_rows": job.total_rows,
            "successful_rows": job.successful_rows,
            "failed_rows": job.failed_rows,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        })

    return jsonify({"data": history}), 200
