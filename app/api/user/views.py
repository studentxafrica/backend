from flask import request, jsonify, g
from app.utils import roles_required
import requests  # type: ignore
from app.models.consumer import Consumer, VerificationRequestStatus
from app import db
from app.models.coupon import Coupon
from app.models.offer import SavedOffer
from typing import List
from flask import current_app
from app.email import send_email


from . import user


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
            'code': coupon.coupon_code,
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
    }
    return jsonify({
        "message": "User profile retrieved successfully",
        "data": user_data
    }), 200


@user.route('/verification/student/<student_id>', methods=['GET'])
@roles_required('admin')
def get_student_verification_details(student_id):
    from app.models import VerificationRequest
    verification_request: VerificationRequest = db.session.query(
        VerificationRequest).filter(
            VerificationRequest.user_id == student_id,
            # VerificationRequest.status == 'pending'
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

    verification_request: VerificationRequest = db.session.query(
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
    user: Consumer = g.user
    if not user:
        return jsonify({"error": "User not found"}), 401

    data = request.get_json()
    if not data or 'documents' not in data:
        return jsonify({"error": "No documents provided"}), 400

    if data.get('personalInfo') is not None and 'dateOfBirth' in data['personalInfo']:
        import datetime
        try:
            date_of_birth_str = data['personalInfo']['dateOfBirth']
            user.date_of_birth = datetime.datetime.strptime(
                date_of_birth_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({"message": "Invalid date format for dateOfBirth"}), 400
        user.save()

    if data['academicInfo'] and 'year' in data['academicInfo'] or 'expectedGraduation' in data['academicInfo']:
        user.graduation_year = data['academicInfo'].get(
            'expectedGraduation', user.graduation_year)
        user.year = data['academicInfo'].get('year', user.year)
        user.save()

    # Create a new verification request
    verification_request = VerificationRequest(
        user_id=user.id,
        verification_type='manual'
    )
    verification_request.save()

    # Process each document
    for doc_data in data['documents']:
        import cloudinary
        import cloudinary.uploader

        cloudinary_resp = cloudinary.uploader.upload(
            doc_data.get('preview'),
            folder='studentx/verification/requests/documents/user-' +
            str(user.id),
        )

        document = VerificationDocument(
            request_id=verification_request.id,
            document_name=doc_data.get('name', 'Document'),
            document_type=doc_data.get('type'),
            document_url=cloudinary_resp.get('secure_url'),
            size=doc_data.get('size', 0)
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

    saved_offer: SavedOffer = db.session.query(SavedOffer).filter(
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
    data: dict = request.get_json()
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
