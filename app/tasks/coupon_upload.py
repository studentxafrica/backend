import csv
from datetime import datetime, timezone
from dateutil import parser  # type: ignore

from app import db
from app.celery_app import celery
from app.models.coupon import Coupon
from app.models.offer import Offer
from app.models.upload_job import UploadJob, UPLOAD_STATUS
from app.utils import generate_qr


def _ensure_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _append_error(job: UploadJob, error: dict):
    if job.errors is None:
        job.errors = []
    job.errors.append(error)


@celery.task(name="coupon_upload.process")
def process_coupon_upload(job_id: str):
    job = db.session.query(UploadJob).filter_by(id=job_id).first()
    if not job:
        return

    offer = db.session.query(Offer).filter_by(id=job.offer_id).first()
    if not offer:
        job.status = UPLOAD_STATUS["FAILED"]
        _append_error(job, {"row": None, "coupon_code": None, "reason": "Offer not found"})
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return

    job.status = UPLOAD_STATUS["PROCESSING"]
    job.errors = []
    db.session.commit()

    try:
        with open(job.file_path, "r", encoding="utf-8-sig", newline="") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader, None)
            if not headers:
                job.mark_failed()
                _append_error(job, {"row": None, "coupon_code": None, "reason": "Empty CSV file"})
                db.session.commit()
                return

            normalized_headers = [h.strip().lower() for h in headers]
            if normalized_headers != ["coupon_code", "expiry_date"]:
                job.mark_failed()
                _append_error(job, {"row": None, "coupon_code": None, "reason": "Invalid CSV headers"})
                db.session.commit()
                return

        # Count total rows
        with open(job.file_path, "r", encoding="utf-8-sig", newline="") as csvfile:
            total_rows = sum(1 for _ in csv.reader(csvfile)) - 1
            job.total_rows = max(total_rows, 0)
            db.session.commit()

        seen_codes = set()
        now = datetime.now(timezone.utc)
        offer_end = _ensure_utc(offer.end_date)

        with open(job.file_path, "r", encoding="utf-8-sig", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row_index, row in enumerate(reader, start=2):
                job.processed_rows += 1

                coupon_code = (row.get("coupon_code") or "").strip()
                expiry_raw = (row.get("expiry_date") or "").strip()

                if not coupon_code:
                    job.failed_rows += 1
                    _append_error(job, {
                        "row": row_index,
                        "coupon_code": coupon_code,
                        "reason": "Missing coupon code"
                    })
                    db.session.commit()
                    continue

                if coupon_code in seen_codes:
                    job.failed_rows += 1
                    _append_error(job, {
                        "row": row_index,
                        "coupon_code": coupon_code,
                        "reason": "Duplicate coupon code in CSV"
                    })
                    db.session.commit()
                    continue

                existing = db.session.query(Coupon).filter_by(coupon_code=coupon_code).first()
                if existing:
                    job.failed_rows += 1
                    _append_error(job, {
                        "row": row_index,
                        "coupon_code": coupon_code,
                        "reason": "Duplicate coupon code"
                    })
                    db.session.commit()
                    continue

                if not expiry_raw:
                    job.failed_rows += 1
                    _append_error(job, {
                        "row": row_index,
                        "coupon_code": coupon_code,
                        "reason": "Missing expiry date"
                    })
                    db.session.commit()
                    continue

                try:
                    expiry_date = _ensure_utc(parser.parse(expiry_raw))
                except (ValueError, TypeError):
                    job.failed_rows += 1
                    _append_error(job, {
                        "row": row_index,
                        "coupon_code": coupon_code,
                        "reason": "Invalid expiry date"
                    })
                    db.session.commit()
                    continue

                if expiry_date <= now:
                    job.failed_rows += 1
                    _append_error(job, {
                        "row": row_index,
                        "coupon_code": coupon_code,
                        "reason": "Expiry date must be in the future"
                    })
                    db.session.commit()
                    continue

                if expiry_date > offer_end:
                    job.failed_rows += 1
                    _append_error(job, {
                        "row": row_index,
                        "coupon_code": coupon_code,
                        "reason": "Expiry date exceeds offer end date"
                    })
                    db.session.commit()
                    continue

                seen_codes.add(coupon_code)

                coupon = Coupon(
                    offer_id=offer.id,
                    consumer_id=None,
                    coupon_code=coupon_code,
                    expiry_date=expiry_date,
                    status='active',
                    qr_code=generate_qr(coupon_code),
                )
                db.session.add(coupon)
                job.successful_rows += 1
                db.session.commit()

        job.mark_completed()
        db.session.commit()

    except FileNotFoundError:
        job.mark_failed()
        _append_error(job, {"row": None, "coupon_code": None, "reason": "CSV file not found"})
        db.session.commit()
