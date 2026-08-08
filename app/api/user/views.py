from flask import request, jsonify, g
from app.utils import roles_required
import requests  # type: ignore
from app.models.consumer import Consumer, VerificationRequestStatus
from app import db
from app.models.coupon import Coupon
from app.models.offer import SavedOffer
from app.models.student_business_application import (
    APPLICATION_DOCUMENT_TYPES,
    APPLICATION_STATUS,
    StudentBusinessApplication,
    StudentBusinessApplicationDocument,
)
from typing import List
from flask import current_app
from app.email import send_email
from datetime import datetime, timezone
import json


from . import user

REQUIRED_PROFILE_FIELDS = [
    # ("phone", "Phone number"),
    ("school", "Institution/School"),
    ("major", "Program/Major"),
    ("graduation_year", "Expected graduation year"),
    ("student_id", "Student ID"),
]


def _build_application_eligibility(user: Consumer):
    missing_requirements = []
    for field_name, label in REQUIRED_PROFILE_FIELDS:
        value = getattr(user, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing_requirements.append({
                "field": field_name,
                "label": label,
                "message": f"Add your {label.lower()} to continue.",
            })

    if not user.verified:
        missing_requirements.append({
            "field": "verification",
            "label": "Student verification",
            "message": "Complete student verification to apply.",
        })

    return {
        "eligible": len(missing_requirements) == 0,
        "missingRequirements": missing_requirements,
    }


def _serialize_student_business_application(application: StudentBusinessApplication | None):
    if not application:
        return None
    return {
        "id": application.id,
        "status": application.status,
        "businessName": application.business_name,
        "businessType": application.business_type,
        "businessDescription": application.business_description,
        "businessEmail": application.business_email,
        "businessPhone": application.business_phone,
        "website": application.website,
        "registrationNumber": application.registration_number,
        "additionalNotes": application.additional_notes,
        "reviewFeedback": application.review_feedback,
        "submittedAt": application.created_at.isoformat() if application.created_at else None,
        "reviewedAt": application.reviewed_at.isoformat() if application.reviewed_at else None,
        "merchantId": application.merchant_id,
        "documents": [{
            "id": doc.id,
            "name": doc.document_name,
            "type": doc.document_type,
            "url": doc.document_url,
            "size": doc.size,
            "verified": doc.verified,
            "uploadedAt": doc.upload_date.isoformat() if doc.upload_date else None,
        } for doc in application.documents]
    }


@user.route('/sheerid/callback', methods=['POST'])
def sheerid_callback():
    data = request.get_json()
    userId = request.args.get('userId')

    if not data or 'verificationId' not in data:
        return jsonify({"error": "Invalid callback data"}), 400

    token = "403fa31043554c4ba524cae60974b93e"  # Replace with your actual token
    verification_id = data['verificationId']

    # Fetch full verification details (including metadata)
    verification_url = f"https://services.sheerid.com/rest/v2/verification/{verification_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        response = requests.get(verification_url, headers=headers)
        response.raise_for_status()  # Raise HTTP errors if any
        verification_data = response.json()

        # Extract metadata (if available)
        metadata = verification_data.get("metadata", {})
        # Should match your SheerID dashboard key
        user_id = metadata.get("userId")
        verification_type = metadata.get("verificationType")

        # TODO: Update your database with user_id and verification status
        # Example: update_user_verification_status(user_id, verification_data)

        return jsonify({
            "message": "Callback processed successfully",
            "userId": user_id,
            "verificationType": verification_type
        }), 200

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error fetching verification details: {e}")
        return jsonify({"error": "Failed to fetch verification details"}), 500


@user.route('/me', methods=['GET'])
@roles_required('consumer')
def get_current_user_profile():
    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401
    user_coupons: List[Coupon] = user.coupons
    saved_offers: List[SavedOffer] = user.saved_offers
    user_data = {
        'id': user.id,
        'firstName': user.first_name,
        'lastName': user.last_name,
        'email': user.email,
        'phone': user.phone,
        'avatar': user.profile_picture,
        'university': user.school,
        'graduationYear': user.graduation_year,
        'dateOfBirth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'major': user.major,
        'studentId': user.student_id,
        'joinDate': user.created_at.isoformat(),
        'location': user.location,
        'bio': user.bio,
        'isVerified': user.verified,
        'verificationStatus': user.verification_status.value if user.verification_status.value else 'pending',
        'savedDeals': [{
            'id': saved.id,
            'offerId': saved.offer.id,
            'title': saved.offer.title,
            'brand': saved.offer.merchant.name,
            'brandLogo': saved.offer.merchant.logo,
            'discount': saved.offer.discount_value,
            'description': saved.offer.description,
            'category': saved.offer.category.name if saved.offer.category else None,
            'originalPrice': 1199,
            'salePrice': 1079,
            'savings': 120,
            'expiryDate': saved.offer.end_date.isoformat(),
            'isLimited': False,
            'savedDate': saved.created_at.isoformat(),
            'rating': 4.8,
            'verified': True
        } for saved in saved_offers],
        'coupons': [{
            'id': coupon.id,
            # Event registrations all share one link, so there is no code to show
            'code': None if coupon.offer.is_event else coupon.coupon_code,
            'offerKind': coupon.offer.offer_kind,
            'eventUrl': coupon.offer.event_url,
            'qrCode': coupon.qr_code,
            'title': coupon.offer.title,
            'brand': coupon.offer.merchant.name,
            'brandLogo': coupon.offer.merchant.logo,
            'discount': coupon.offer.discount_value,
            'discountType': coupon.offer.discount_type,
            'description': coupon.offer.description,
            'expiryDate': coupon.expiry_date.isoformat(),
            'status': coupon.status,
            'redemptionType': coupon.offer.redemption_type,
            'category': {
                'id': coupon.offer.category.id if coupon.offer.category else None,
                'name': coupon.offer.category.name if coupon.offer.category else None
            },
            'savings': 45.99
        } for coupon in user_coupons],
        'verificationLevel': user.profile_complete,
        'totalSavings': 1247,
        'dealsUsed': len([coupon for coupon in user.coupons if coupon.status == 'redeemed']),
        'favoriteCategories': ["Technology", "Food & Dining", "Fashion"],
        'studentBusinessPromotion': {
            'enabled': True,
            'title': 'Launch your business on StudentX',
            'description': 'Create a student-owned merchant profile and start sharing your products or freelance services with fellow students.',
            'ctaLabel': 'Become a Student Merchant',
            'ctaUrl': 'https://merchant.studentx.co.ke/register?merchantType=student-owned&source=student-profile',
        },
    }
    return jsonify({
        "message": "User profile retrieved successfully",
        "data": user_data
    }), 200


@user.route('/student-business-application/eligibility', methods=['GET'])
@roles_required('consumer')
def get_student_business_application_eligibility():
    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401

    latest_application = db.session.query(StudentBusinessApplication).filter(
        StudentBusinessApplication.consumer_id == user.id
    ).order_by(StudentBusinessApplication.created_at.desc()).first()

    eligibility = _build_application_eligibility(user)
    return jsonify({
        "message": "Eligibility retrieved successfully",
        "data": {
            **eligibility,
            "latestApplication": _serialize_student_business_application(latest_application),
        }
    }), 200


@user.route('/student-business-applications/latest', methods=['GET'])
@roles_required('consumer')
def get_latest_student_business_application():
    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401

    latest_application = db.session.query(StudentBusinessApplication).filter(
        StudentBusinessApplication.consumer_id == user.id
    ).order_by(StudentBusinessApplication.created_at.desc()).first()

    if not latest_application:
        return jsonify({
            "message": "No application found",
            "data": None
        }), 200

    return jsonify({
        "message": "Application retrieved successfully",
        "data": _serialize_student_business_application(latest_application)
    }), 200


@user.route('/student-business-applications', methods=['POST'])
@roles_required('consumer')
def submit_student_business_application():
    import cloudinary.uploader  # type: ignore

    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401

    eligibility = _build_application_eligibility(user)
    if not eligibility["eligible"]:
        return jsonify({
            "message": "You are not eligible to submit this application yet",
            "data": eligibility
        }), 403

    latest_application = db.session.query(StudentBusinessApplication).filter(
        StudentBusinessApplication.consumer_id == user.id
    ).order_by(StudentBusinessApplication.created_at.desc()).first()

    if latest_application and latest_application.status in [
        APPLICATION_STATUS["PENDING"],
        APPLICATION_STATUS["APPROVED"],
    ]:
        return jsonify({
            "message": "You already have an active application",
            "data": _serialize_student_business_application(latest_application)
        }), 409

    business_name = (request.form.get("businessName") or "").strip()
    business_type = (request.form.get("businessType") or "").strip()
    business_description = (request.form.get("businessDescription") or "").strip()
    business_email = (request.form.get("businessEmail") or user.email).strip() or None
    business_phone = (request.form.get("businessPhone") or user.phone or "").strip() or None
    website = (request.form.get("website") or "").strip() or None
    registration_number = (request.form.get("registrationNumber") or "").strip() or None
    additional_notes = (request.form.get("additionalNotes") or "").strip() or None

    if not business_name or not business_type or not business_description:
        return jsonify({
            "message": "Missing required fields",
            "description": "businessName, businessType and businessDescription are required"
        }), 400

    ownership_documents = request.files.getlist("ownershipDocuments")
    if not ownership_documents:
        return jsonify({
            "message": "At least one ownership document is required"
        }), 400

    documents_meta_str = request.form.get("documentsMeta")
    documents_meta = json.loads(documents_meta_str) if documents_meta_str else []

    application = StudentBusinessApplication(
        consumer_id=user.id,
        business_name=business_name,
        business_type=business_type,
        business_description=business_description,
        business_email=business_email,
        business_phone=business_phone,
        website=website,
        registration_number=registration_number,
        additional_notes=additional_notes,
        status=APPLICATION_STATUS["PENDING"],
    )
    db.session.flush()

    for idx, file in enumerate(ownership_documents):
        meta = documents_meta[idx] if idx < len(documents_meta) else {}
        document_type = meta.get("type") or APPLICATION_DOCUMENT_TYPES["OWNERSHIP_PROOF"]
        if document_type not in APPLICATION_DOCUMENT_TYPES.values():
            document_type = APPLICATION_DOCUMENT_TYPES["OTHER"]

        cloudinary_resp = cloudinary.uploader.upload(
            file,
            folder=f"studentx/business-applications/documents/user-{user.id}",
            resource_type="auto"
        )
        StudentBusinessApplicationDocument(
            application_id=application.id,
            document_name=meta.get("name") or file.filename or "Ownership Document",
            document_type=document_type,
            document_url=cloudinary_resp.get("secure_url"),
            size=str(meta.get("size") or getattr(file, "content_length", "") or ""),
        )

    db.session.commit()

    send_email(
        to=[user.email],
        subject="StudentX Business Application Received",
        template="email/student_business_application_submitted",
        context={
            "student_name": user.first_name,
            "business_name": application.business_name,
            "application_id": application.id,
        }
    )

    return jsonify({
        "message": "Application submitted successfully",
        "data": _serialize_student_business_application(application)
    }), 201


@user.route('/verification/student/<student_id>', methods=['GET'])
@roles_required('admin')
def get_student_verification_details(student_id):
    from app.models import VerificationRequest
    verification_request: VerificationRequest | None = db.session.query(
        VerificationRequest).filter(
            VerificationRequest.user_id == student_id,
            # VerificationRequest.status == 'pending' TODO
    ).order_by(VerificationRequest.created_at.desc()).first()
    if not verification_request:
        return jsonify({"message": "Student has not submitted a verification request"}), 404

    verification_details = {
        'id': verification_request.id,
        'student': {
            'id': verification_request.user.id,
            'firstName': verification_request.user.first_name,
            'lastName': verification_request.user.last_name,
            'email': verification_request.user.email,
            'studentId': verification_request.user.student_id,
            'phoneNumber': verification_request.user.phone,
            'program': verification_request.user.major,
            'year': verification_request.user.year,
            'institution': verification_request.user.school,
            'dateOfBirth': getattr(verification_request.user, 'date_of_birth', None),
            'expectedGraduation': getattr(verification_request.user, 'graduation_year', None),
            'verified': verification_request.user.verified,
            'verificationStatus': verification_request.user.verification_status.value if verification_request.user.verification_status else 'pending',
        },
        'submissionDate': verification_request.user.created_at.isoformat() if verification_request.user.created_at else None,
        'documents': [
            {
                'id': doc.id,
                'name': doc.document_name,
                'type': doc.document_type,
                'url': doc.document_url,
                'uploadDate': doc.upload_date.isoformat() if doc.upload_date else None,
                'verified': doc.verified,
                'size': doc.size
            } for doc in verification_request.documents
        ],
        'previousRequests': len(verification_request.user.verification_requests),
        'notes': [
            {
                'id': note.id,
                'comment': note.comment,
                'createdAt': note.created_at.isoformat() if note.created_at else None,
                'reviewer': {
                    'id': note.review.reviewer.id if note.review and note.review.reviewer else None,
                    'name': note.review.reviewer.first_name if note.review and note.review.reviewer else None
                }
            } for review in verification_request.reviews
            for note in review.notes
        ] if verification_request.reviews else [],
    }

    return jsonify({
        "message": "Verification details retrieved successfully",
        "data": verification_details
    }), 200


@user.route('/verification/student/action', methods=['POST'])
@roles_required('admin')
def process_student_verification_request():
    from app.models import VerificationRequest, VerificationReview, VerificationReviewNote
    data = request.get_json()
    print("Received data:", data)
    if not data or 'requestId' not in data or 'action' not in data:
        return jsonify({"error": "Invalid request data"}), 400

    request_id = data['requestId']
    action = data['action']
    feedback = data.get('feedback')
    review_note = data.get('reviewNote')

    if not feedback:
        return jsonify({"error": "Feedback message is required"}), 400

    verification_request: VerificationRequest | None = db.session.query(
        VerificationRequest).filter_by(id=request_id).first()
    if not verification_request:
        return jsonify({"error": "Verification request not found"}), 404

    if action not in ['approve', 'reject', 'request']:
        return jsonify({"error": "Invalid action"}), 400

    # Update the verification request status
    if action == 'approve':
        verification_request.status = 'approved'
        verification_request.user.verification_status = VerificationRequestStatus.APPROVED
        verification_request.user.verified_at = verification_request.created_at
    elif action == 'reject':
        verification_request.status = 'rejected'
        verification_request.user.verified_at = None
        verification_request.user.verification_status = VerificationRequestStatus.REJECTED
    elif action == 'request':
        verification_request.status = 'requested'
        verification_request.user.verified_at = None
        verification_request.user.verification_status = VerificationRequestStatus.REQUESTED
    verification_request.save()
    verification_request.user.save()

    async def delete_cloudinary_documents(request_id):
        from app.models import VerificationDocument
        import cloudinary
        import cloudinary.uploader

        documents: list[VerificationDocument] = db.session.query(VerificationDocument).filter_by(
            request_id=request_id).all()
        for doc in documents:
            if doc.document_url:
                public_id = doc.document_url.split('/')[-1].split('.')[0]
                print(f"Deleting document with public_id: {public_id}")
                cloudinary.uploader.destroy(public_id, invalidate=True)

            doc.delete()

    # Delete documents from Cloudinary if the request is approved or rejected
    if action in ['approve', 'reject']:
        import asyncio
        asyncio.run(delete_cloudinary_documents(request_id))

    # Create a review entry
    review = VerificationReview(
        request_id=verification_request.id,
        reviewer_id=g.user.id,
        review_date=verification_request.created_at,
        status='approved' if action == 'approve' else 'rejected' if action == 'reject' else 'request',
        feedback=review_note
    )
    review.save()

    # Ensure feedback preserves formatting in the email template
    # Pass both the raw feedback and a version with line breaks replaced by <br> for HTML emails
    import markupsafe
    send_email(
        to=[verification_request.user.email],
        subject="Verification Request Reviewed",
        template="email/verification_review",
        context={
            'feedback': feedback,
            'feedback_html': markupsafe.Markup(feedback.replace('\n', '<br>')) if feedback else ''
        }
    )

    # Add a note to the review if feedback is provided
    if review_note:
        note = VerificationReviewNote(
            review_id=review.id,
            comment=review_note
        )
        note.save()

    return jsonify({
        "message": "Verification request processed successfully",
        "data": {
            "requestId": verification_request.id,
            "status": verification_request.status,
            "reviewId": review.id
        }
    }), 200


@user.route('/verification/student/submit', methods=['POST'])
@roles_required('consumer')
def submit_student_verification_request():
    from app.models import VerificationRequest, VerificationDocument
    import json
    import datetime
    import cloudinary
    import cloudinary.uploader

    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401

    # Handle multipart/form-data
    personal_info_str = request.form.get('personalInfo')
    academic_info_str = request.form.get('academicInfo')
    documents_meta_str = request.form.get('documentsMeta')
    files = request.files.getlist('documents')

    if not files or len(files) == 0:
        return jsonify({"error": "No documents provided"}), 400

    # Parse JSON strings
    personal_info = json.loads(personal_info_str) if personal_info_str else {}
    academic_info = json.loads(academic_info_str) if academic_info_str else {}
    documents_meta = json.loads(documents_meta_str) if documents_meta_str else []

    # Update personal info
    if personal_info.get('dateOfBirth'):
        try:
            date_of_birth_str = personal_info['dateOfBirth']
            user.date_of_birth = datetime.datetime.strptime(
                date_of_birth_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({"message": "Invalid date format for dateOfBirth"}), 400
        user.save()

    # Update academic info
    if academic_info:
        if 'expectedGraduation' in academic_info:
            user.graduation_year = academic_info.get('expectedGraduation', user.graduation_year)
        if 'year' in academic_info:
            user.year = academic_info.get('year', user.year)
        if 'studentId' in academic_info:
            user.student_id = academic_info.get('studentId', user.student_id)
        if 'program' in academic_info:
            user.major = academic_info.get('program', user.major)
        user.save()

    # Create a new verification request
    verification_request = VerificationRequest(
        user_id=user.id,
        verification_type='manual'
    )
    verification_request.save()

    # Process each uploaded file
    for i, file in enumerate(files):
        # Get metadata for this file (if available)
        meta = documents_meta[i] if i < len(documents_meta) else {}

        # Upload file to Cloudinary
        cloudinary_resp = cloudinary.uploader.upload(
            file,
            folder='studentx/verification/requests/documents/user-' + str(user.id),
            resource_type='auto'
        )

        document = VerificationDocument(
            request_id=verification_request.id,
            document_name=meta.get('name', file.filename or 'Document'),
            document_type=meta.get('type'),
            document_url=cloudinary_resp.get('secure_url'),
            size=meta.get('size', 0)
        )
        document.save()

    user.verification_status = VerificationRequestStatus.IN_PROGRESS
    user.save()

    send_email(
        to=[user.email],
        subject="Verification Request Submitted",
        template="email/verification_request",
        context={
            'user': user,
            'verification_request': verification_request,
            'documents': [doc.document_url for doc in verification_request.documents]
        }
    )

    return jsonify({
        "message": "Verification request submitted successfully",
        "data": {
            "requestId": verification_request.id,
            "submissionDate": verification_request.created_at.isoformat()
        }
    }), 201


@user.route('/me', methods=['PUT'])
@roles_required('consumer')
def update_current_user_profile():

    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    ALLOWED_UPDATE_FIELDS = {
        'first_name': str,
        'last_name': str,
        'email': str,
        'phone': str,
        'school': str,
        'graduation_year': str,
        'date_of_birth': str,
        'major': str,
        'student_id': str,
        'location': str,
        'bio': str,
        'profile_picture': str
    }

    # Update user attributes
    for key, value in data.items():
        if hasattr(user, key) and key in ALLOWED_UPDATE_FIELDS:
            setattr(user, key, value)

    user.save()

    return jsonify({
        "message": "User profile updated successfully",
        "data": {
            'id': user.id,
            'firstName': user.first_name,
            'lastName': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'avatar': user.profile_picture,
            'university': user.school,
            'graduationYear': user.graduation_year,
            'dateOfBirth': user.date_of_birth.isoformat() if user.date_of_birth else None,
            'major': user.major,
            'studentId': user.student_id,
            'joinDate': user.created_at.isoformat(),
            'location': user.location,
            'bio': user.bio,
            'isVerified': user.verified
        }
    }), 200


@user.route("/me/saved-offers", methods=["GET"])
@roles_required('consumer')
def get_saved_offers():

    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401
    saved_offers: List[SavedOffer] = user.saved_offers
    saved_offers_data = [{
        'id': saved.id,
        'title': saved.offer.title,
        'brand': saved.offer.merchant.name,
        'brandLogo': saved.offer.merchant.logo,
        'discount': saved.offer.discount_value,
        'description': saved.offer.description,
        'category': saved.offer.category.name,
        'originalPrice': 1199,
        'salePrice': 1079,
        'savings': 120,
        'expiryDate': saved.offer.expiry_date.isoformat(),
        'isLimited': False,
        'savedDate': saved.created_at.isoformat(),
        'rating': 4.8,
        'verified': True
    } for saved in saved_offers]
    return jsonify({
        "message": "Saved offers retrieved successfully",
        "data": saved_offers_data
    }), 200


@user.route("/me/saved-offers/<offer_id>", methods=["DELETE"])
@roles_required('consumer')
def delete_saved_offer(offer_id):

    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401

    saved_offer: SavedOffer | None = db.session.query(SavedOffer).filter(
        SavedOffer.id == offer_id,
        SavedOffer.consumer_id == user.id
    ).first()
    if not saved_offer:
        return jsonify({"error": "Saved offer not found"}), 404

    saved_offer.delete()

    return jsonify({
        "message": "Saved offer deleted successfully"
    }), 200


@user.route('/testimonials', methods=['GET', 'POST'])
def user_testimonials():
    if request.method == 'GET':
        limit = request.args.get('limit', default=5, type=int)
        from app.models import Testimonial
        testimonials = db.session.query(Testimonial).limit(limit).all()
        return jsonify({
            "message": "Testimonials retrieved successfully",
            "data": [testimonial.to_json() for testimonial in testimonials]
        }), 200
    data: dict | None = request.get_json()
    if not data or 'review' not in data or 'rating' not in data:
        return jsonify({"message": "Missing required fields"}), 400

    from app.models import Testimonial
    testimonial = Testimonial(
        name=data.get('name', 'Anonymous'),
        university=data.get('university'),
        review=data.get('review'),
        rating=data.get('rating', 4)
    )
    testimonial.save()

    return jsonify({
        "message": "Testimonial created successfully",
    }), 201
