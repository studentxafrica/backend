from flask import Blueprint
from flask import request, jsonify, make_response
from flask_jwt_extended import create_access_token, jwt_required
from flasgger import swag_from  # type: ignore
from app.models import Consumer, Merchant

auth = Blueprint('auth', __name__)


@auth.post('/user/login')
@swag_from('docs/login.yml')
def login():
    """
    Login route.
    Scenarios:
        - User login with valid credentials
        - User login with invalid credentials
        - User login with missing credentials
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


@auth.post('/user/consumer/register')
@swag_from('docs/register-consumer.yml')
def register_consumer():
    """
    Consumer registration route.
    Scenarios:
    - Successful registration
    - Registration with existing email
    - Registration with missing fields
    """
    try:
        data: dict = request.get_json()
        if not data:
            return jsonify({"message": "Missing JSON in request"}), 400
        if 'email' not in data or 'password' not in data:
            return jsonify({"message": "Missing email or password"}), 400

        from app import db
        if db.session.query(Consumer).filter_by(
            email=data.get('email')
        ).first():
            return jsonify({"message": "Email already exists"}), 409
        consumer = Consumer(
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            school=data.get('school'),
            password=data.get('password'),
        )
        consumer.save()
        print(consumer.to_json())
        print(consumer.first_name)
        return jsonify({
            "message": "User registered successfully",
            "username": consumer.first_name
        }), 201
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "message": "Uh-oh, something went wrong.",
            "description": "Please try again later. It's not you, it's us.",
        }), 500
