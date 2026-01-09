import os
from flask import request, jsonify, make_response
from flask_jwt_extended import create_access_token, jwt_required
from flasgger import swag_from
from app.models import Consumer, Merchant
from . import auth


@auth.post('/user/login')
def login():
    """
    Login route for consumers.
    ---
    tags:
        - Auth
    summary: Consumer login
    description: Login route for consumers to authenticate and receive a JWT token.
    parameters:
        - in: body
          name: body
          required: true
          schema:
            type: object
            properties:
              email:
                type: string
                format: email
                example: john.doe@example.com
            password:
                type: string
                format: password
                example: securepassword123
    responses:
        200:
            description: Login successful
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Login successful
                    user:
                        type: object
                        properties:
                            id:
                                type: integer
                                example: 1
                            first_name:
                                type: string
                                example: John
                            last_name:
                                type: string
                                example: Doe
                            email:
                                type: string
                                format: email
                                example: john.doe@example.com
                    user_role:
                        type: string
                        example: consumer
        400:
            description: Missing JSON in request or missing email/password
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Missing JSON in request
        401:
            description: Invalid email or password
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Invalid email or password
    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing JSON in request"}), 400
    if 'email' not in data or 'password' not in data:
        return jsonify({"message": "Missing email or password"}), 400

    from app import db
    user: Consumer = db.session.query(Consumer).filter_by(
        email=data.get('email')
    ).first()

    if not user or not user.verify_password(data.get('password')):
        return jsonify({"message": "Invalid email or password"}), 401
    response = make_response(
        jsonify({
            "message": "Login successful",
            "user": user.to_json(),
            "user_role": "consumer",
        }),
        200
    )
    response.set_cookie(
        'access_token',
        value=create_access_token(identity=user.id),
        httponly=True,
        secure=True,
        samesite='None'
    )
    return response


@auth.post('/merchant/login')
def merchant_login():
    """
    Merchant login route.
    ---
    tags:
        - Auth
    summary: Merchant login
    description: Login route for merchants to authenticate and receive a JWT token.
    parameters:
        - in: body
          name: body
          required: true
          schema:
            type: object
            properties:
              email:
                type: string
                format: email
                example: merchant@example.com
            password:
                type: string
                format: password
                example: securepassword123
    responses:
        200:
            description: Login successful
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Login successful
                    user:
                        type: object
                        properties:
                            name:
                                type: string
                                example: Merchant Name
                            email:
                                type: string
                                format: email
                                example: merchant@example.com
                            logo:
                                type: string
                                example: https://example.com/logo.png
                            website:
                                type: string
                                example: https://merchant-website.com
                            phone:
                                type: string
                                example: +1234567890
                            address:
                                type: string
                                example: 123 Merchant St, City, Country
                            city:
                                type: string
                                example: City Name
                            country:
                                type: string
                                example: Country Name
                            zip_code:
                                type: string
                                example: 12345
                            approved:
                                type: boolean
                                example: true
                            approved_on:
                                type: string
                                format: date-time
                                example: '2023-10-01T12:00:00Z'
                            email_verified:
                                type: boolean
                                example: true
                            email_verified_on:
                                type: string
                                format: date-time
                                example: '2023-10-01T12:00:00Z'
                            rating:
                                type: number
                                format: float
                                example: 4.5
                            category:
                                type: object
                                properties:
                                    id:
                                        type: integer
                                        example: 1
                                    name:
                                        type: string
                                        example: Retail
        400:
            description: Missing JSON in request or missing email/password
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Missing JSON in request
        401:
            description: Invalid email or password
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Invalid email or password

    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing JSON in request"}), 400
    if 'email' not in data or 'password' not in data:
        return jsonify({"message": "Missing email or password"}), 400

    from app import db
    user: Merchant = db.session.query(Merchant).filter_by(
        email=data.get('email')
    ).first()

    # user.password = 'Pa$$word1'
    # user.save()  # This line is just for testing purposes, remove it in production

    if not user or not user.verify_password(data.get('password')):
        return jsonify({"message": "Invalid email or password"}), 401
    user_data = {
        'id': getattr(user, 'id', None),
        'name': getattr(user, 'name', None),
        'email': getattr(user, 'email', None),
        'website': getattr(user, 'website', None),
        'phone': getattr(user, 'phone', None),
        'logo': getattr(user, 'logo', None),
        'joinDate': getattr(user, 'created_at', None).isoformat() if user.created_at else None,
        'preferredCurrency': getattr(user, 'preferred_currency', None),
        'address': getattr(user, 'address', None),
        'city': getattr(user, 'city', None),
        'country': getattr(user, 'country', None),
        'zipcode': getattr(user, 'zip_code', None),
        'isApproved': getattr(user, 'approved', None),
        'emailVerified': getattr(user, 'email_verified', None),
        "rating": getattr(user, "rating", None),
        "category": {
            "id": getattr(user, 'category', None).id if getattr(user, 'category', None) else None,
            "name": getattr(user, 'category', None).name if getattr(user, 'category', None) else None,
        }
    }
    response = make_response(
        jsonify({
            "message": "Login successful",
            "user": user_data,
            "user_role": "merchant",
        }),
        200
    )
    response.set_cookie(
        'access_token',
        value=create_access_token(identity=user.id),
        httponly=True,
        secure=True,
        samesite='None'
    )
    return response


@auth.post('/admin/login')
@swag_from('docs/login.yml')
def admin_login():
    """
    Login route.
    Scenarios:
        - User login with valid credentials
        - User login with invalid credentials
        - User login with missing credentials
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not data:
        return jsonify({"message": "Missing JSON in request"}), 400
    if 'username' not in data or 'password' not in data:
        return jsonify({"message": "Missing email or password"}), 400

    from app.models import Administrator
    from app import db
    user: Administrator = db.session.query(Administrator).filter_by(
        username=username
    ).first()
    if not user or not user.verify_password(password):
        return jsonify({"message": "Invalid email or password"}), 401

    user_data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "username": user.username,
        'phone': user.phone_number,
        'profileImage': user.profile_image,
        'lastLogin': user.last_login.isoformat() if user.last_login else None,
    }
    response = make_response(
        jsonify({
            "message": "Login successful",
            "user": user_data,
            "user_role": "admin",
            "user_type": user.role.value
        }),
        200
    )
    response.set_cookie(
        'access_token',
        value=create_access_token(identity=user.id),
        httponly=True,
        secure=True,
        samesite='None'
    )
    return response


@auth.post('/user/consumer/register')
@swag_from('docs/registration.yml', endpoint='register')
def register_consumer():
    """
    Consumer registration route.
    Scenarios:
    - Successful registration
    - Registration with existing email
    - Registration with missing fields
    """
    data: dict = request.get_json()
    if not data:
        return jsonify({"message": "Missing JSON in request"}), 400
    if 'email' not in data or 'password' not in data:
        return jsonify({"message": "Missing email or password"}), 400

    from app import db
    from app.email import send_email
    consumer = db.session.query(Consumer).filter_by(
        email=data.get('email')
    ).first()
    if consumer:
        return jsonify({"message": "Email already exists"}), 409
    consumer = Consumer(
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email=data.get('email'),
        school=data.get('school'),
        password=data.get('password'),
    )
    consumer.save()
    send_email(
        subject="Welcome to StudentX!",
        to=[consumer.email],
        template="email/consumer_welcome",
        context={"name": consumer.first_name}
    )
    return jsonify({
        "message": "User registered successfully",
        "username": consumer.first_name
    }), 201


@auth.post('/user/merchant/verify-email')
@jwt_required()
def verify_merchant_email(merchant_id=None):
    """
    Verify the email of a merchant.
    ---
    tags:
        - Auth
    summary: Verify merchant email
    description: Sends a verification email to the merchant's email address.
    responses:
        200:
            description: Email verification sent successfully
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Email verified successfully
        401:
            description: User not found or email already verified
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: User not found or email already verified
        400:
            description: Token is required or invalid/expired token
            schema:
                type: object
                properties:
                    message:
                        type: string
                        example: Token is required or invalid/expired token

    """
    from app import db
    from flask_jwt_extended import get_jwt_identity

    user_id = merchant_id or get_jwt_identity()
    user: Merchant = db.session.query(Merchant).filter_by(id=user_id).first()

    if not user:
        return jsonify({"message": "User not found"}), 401

    if user.email_verified:
        return jsonify({"message": "Email already verified"}), 200

    from app.email import generate_confirmation_token, send_email
    token = generate_confirmation_token(user.email)
    confirm_url = f"{os.environ.get('FRONTEND_BASE_URL', 'https://studentx.co.ke')}/auth/merchant/confirm-email?token={token}"
    send_email(
        subject="Please confirm your email",
        to=[user.email],
        template="email/verify_email",
        context={
            "confirm_url": confirm_url,
            "name": user.name
        }
    )

    return jsonify({"message": "Email verified successfully"}), 200


@auth.get('/user/merchant/confirm-email')
@swag_from('docs/confirm-email.yml')
def confirm_merchant_email():
    """
    Confirm the email of a merchant.
    Scenarios:
        - Successful email confirmation
        - Invalid or expired token
    """
    from app import db
    from app.email import confirm_token

    token = request.args.get('token')
    if not token:
        return jsonify({"message": "Token is required"}), 400

    email = confirm_token(token)
    if not email:
        return jsonify({"message": "Invalid or expired token"}), 400

    user: Merchant = db.session.query(Merchant).filter_by(email=email).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    user.email_verified = True
    user.email_verified_on = db.func.now()
    user.save()

    return jsonify({"message": "Email confirmed successfully"}), 200


@auth.post('/user/reset-password')
def reset_password():
    """
    Reset password for a user.
    Scenarios:
        - Successful password reset
        - User not found
        - Invalid or expired token
    """
    from app import db
    from app.email import send_email, generate_confirmation_token, confirm_token

    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({"message": "Missing email"}), 400

    user = db.session.query(Consumer).filter_by(email=data['email']).first()
    if not user:
        user = db.session.query(Merchant).filter_by(email=data['email']).first()
    if user:
        try:
            token = generate_confirmation_token(user.email)
            reset_url = f"{os.environ.get('FRONTEND_BASE_URL', 'https://studentx.co.ke')}/auth/user/confirm-reset-password?token={token}"
            from datetime import datetime
            resp = send_email(
                subject="Reset your password",
                to=[user.email],
                template="email/reset_password",
                context={
                    "reset_link": reset_url,
                    'current_year': datetime.now().year,
                    "name": user.first_name if hasattr(user, 'first_name') else user.name,
                }
            )
            if not resp:
                return jsonify({"message": "Failed to send reset email"}), 500
        except Exception as e:
            return jsonify({"message": "Failed to send reset email"}), 500

    return jsonify({"message": "Password reset email sent successfully"}), 200


@auth.route('/user/confirm-reset-password', methods=['POST'])
def confirm_reset_password():
    """
    Confirm the password reset for a user.
    Scenarios:
        - Successful password reset
        - Invalid or expired token
    """
    from app import db
    from app.email import confirm_token

    token = request.args.get('token')
    if not token:
        return jsonify({"message": "Token is required"}), 400

    email = confirm_token(token)
    if not email:
        return jsonify({"message": "Invalid or expired token"}), 400

    user: Consumer = db.session.query(Consumer).filter_by(email=email).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    password = request.json.get('password')
    if not password:
        return jsonify({"message": "Password is required"}), 400
    user.password = password
    user.save()

    return jsonify({
        "message": "Password reset successful",
        "email": user.email
    }), 200
