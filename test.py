import io
import os

import cloudinary
import cloudinary.uploader
import dotenv
import qrcode

dotenv.load_dotenv()

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
)


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
    img = qr.make_image(fill="black", back_color="white")

    # 2) save it into a BytesIO buffer
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # 3) upload the buffer
    upload_result = cloudinary.uploader.upload(
        buf,
        folder="studentx/coupons/qrcodes",
        resource_type="image",  # ensure it's treated as an image
    )
    return upload_result.get("secure_url")


res = generate_qr("STUDENTX-TEST")

print(res)
