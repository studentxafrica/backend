from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import requests  # type: ignore
from app.models.consumer import Consumer
from app import db


from . import user


@user.route('/sheerid/callback', methods=['POST'])
def sheerid_callback():
    data = request.get_json()
    userId = request.args.get('userId')
    print(f"User ID from query parameters: {userId}")
    print("Received SheerID callback data:", data)

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

        print("Full verification details:", verification_data)

        # Extract metadata (if available)
        metadata = verification_data.get("metadata", {})
        # Should match your SheerID dashboard key
        user_id = metadata.get("userId")
        verification_type = metadata.get("verificationType")

        print(
            f"Metadata received: userId={user_id}, verificationType={verification_type}")

        # TODO: Update your database with user_id and verification status
        # Example: update_user_verification_status(user_id, verification_data)

        return jsonify({
            "message": "Callback processed successfully",
            "userId": user_id,
            "verificationType": verification_type
        }), 200

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch verification details: {e}")
        return jsonify({"error": "Failed to fetch verification details"}), 500


@user.route('/me', methods=['GET'])
@jwt_required(locations=["cookies"])
def get_current_user_profile():
    user_id = get_jwt_identity()
    user: Consumer = db.session.query(Consumer).filter_by(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
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
        'isVerified': user.verified,
        'verificationLevel': 85,
        'totalSavings': 1247,
        'dealsUsed': len([coupon for coupon in user.coupons if coupon.status == 'redeemed']),
        'favoriteCategories': ["Technology", "Food & Dining", "Fashion"],
    }
    return jsonify({
        "message": "User profile retrieved successfully",
        "data": user_data
    }), 200


@user.route('/me', methods=['PUT'])
def update_current_user_profile():
    pass


@user.route('/me', methods=['DELETE'])
def delete_current_user_profile():
    pass
