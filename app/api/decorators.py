from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app import db  # Assuming you have a User model defined in app/models.py

def verified_student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request(locations=["cookies"])
        user_id = get_jwt_identity()
        
        user = db.session.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if not getattr(user, "verified", False):
            return jsonify({"error": "User not verified"}), 403

        return fn(*args, **kwargs)
    return wrapper
