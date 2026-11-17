"""Kenyan mobile number handling."""
import re

_KENYAN_MOBILE = re.compile(r"^(?:\+?254|0)?([17]\d{8})$")


def normalise_kenyan_mobile(raw: str | None) -> str | None:
    """
    Return the number as +254XXXXXXXXX, or None if it is not a Kenyan mobile
    number. Accepts 07…, 01…, 2547…, +2547… with spaces or dashes.
    """
    if not raw:
        return None
    digits = re.sub(r"[\s\-()]", "", str(raw))
    match = _KENYAN_MOBILE.match(digits)
    return f"+254{match.group(1)}" if match else None


def mask_phone(phone: str | None) -> str | None:
    """+254712345678 -> 0712 ••• 678, for showing a member where airtime goes."""
    if not phone or len(phone) < 13:
        return None
    local = "0" + phone[4:]
    return f"{local[:4]} ••• {local[-3:]}"
