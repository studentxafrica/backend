import io
import cloudinary.uploader  # type: ignore
import cloudinary  # type: ignore
import qrcode  # type: ignore
import hashlib
import base64
import random
import string


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
