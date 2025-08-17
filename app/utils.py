from jwt.exceptions import PyJWTError
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask import jsonify, g
from functools import wraps
import io
import cloudinary.uploader  # type: ignore
import cloudinary  # type: ignore
import qrcode  # type: ignore
import hashlib
import base64
import random
import string
from app.models import Consumer, Merchant, Administrator
from app import db


def base58_encode(b: bytes) -> str:
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    num = int.from_bytes(b, 'big')
    encoded = ''
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = alphabet[rem] + encoded
    return encoded


def generate_coupon_code(provider_id: str, user_id: str = '', length: int = 10) -> str:
    # Combine identifiers
    raw = f"{provider_id}:{user_id}:{random.randint(100000, 999999)}"

    # Hash with SHA-256
    hash_digest = hashlib.sha256(raw.encode()).digest()

    # Encode with Base58
    code = base58_encode(hash_digest)

    # Return the first `length` characters
    return code[:length]


def generate_qr(data):
    # 1) build the QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    # 2) save it into a BytesIO buffer
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # 3) upload the buffer
    upload_result = cloudinary.uploader.upload(
        buf,
        folder='studentx/coupons/qrcodes',
        resource_type="image"             # ensure it's treated as an image
    )
    return upload_result.get('secure_url')


def roles_required(*allowed_roles):
    """
    Universal decorator handling:
    - Admin (username in JWT)
    - Merchant/Consumer (ID in JWT)
    - Secure cookie validation
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            verify_jwt_in_request(locations=['cookies', 'headers'])
            identity = get_jwt_identity()
            
            if not identity:
                return jsonify({"message": "Missing user identity"}), 401

            user = None
            user_type = None

            try:
                user_id = identity
                if 'admin' in allowed_roles:
                    user = db.session.query(Administrator).get(identity)
                    if user:
                        user_type = 'admin'

                if not user and 'merchant' in allowed_roles:
                    user = db.session.query(Merchant).get(user_id)
                    if user:
                        user_type = 'merchant'

                if not user and 'consumer' in allowed_roles:
                    user = db.session.query(Consumer).get(user_id)
                    if user:
                        user_type = 'consumer'
            except ValueError:
                pass  # Expected for admin username case

            if not user:
                return jsonify({"msg": "User not found"}), 401

            if user_type not in allowed_roles:
                return jsonify({"msg": "Insufficient permissions"}), 403

            # 6. Store context
            g.user = user
            g.user_type = user_type
            g.is_admin = (user_type == 'admin')

            return f(*args, **kwargs)

        return decorated_function
    return decorator
