"""
Signing secrets, password-bound tokens and session checks.

Access tokens and password-reset tokens carry a fingerprint of the account's
current password hash. Changing the password changes the hash, so every token
issued before the change stops working: reset links become single-use and
existing sessions are signed out.
"""
import hashlib
import hmac

from flask import current_app
from flask_jwt_extended import create_access_token
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Claim in the access token holding the password fingerprint.
PASSWORD_CLAIM = "pwd"

# Token purposes. Each purpose signs with its own salt, so a token issued for
# one purpose is rejected everywhere else.
EMAIL_CONFIRMATION = "email-confirmation"
PASSWORD_RESET = "password-reset"

TOKEN_MAX_AGE_SECONDS = 3600

# Secrets that must come from the environment.
REQUIRED_SECRETS = ("SECRET_KEY", "JWT_SECRET_KEY", "SECURITY_PASSWORD_SALT")
MIN_SECRET_LENGTH = 32


def check_signing_secrets(config) -> None:
    """
    Refuse to start when a signing secret is missing or too short.

    Only names are reported, never values.
    """
    missing = [name for name in REQUIRED_SECRETS if not config.get(name)]
    if missing:
        raise RuntimeError(
            "Missing required settings: " + ", ".join(missing) + ". "
            "Set them in the environment or the .env file. Generate each value with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    too_short = [
        name for name in REQUIRED_SECRETS
        if len(str(config.get(name))) < MIN_SECRET_LENGTH
    ]
    if too_short:
        raise RuntimeError(
            "These settings must be at least "
            f"{MIN_SECRET_LENGTH} characters long: " + ", ".join(too_short) + "."
        )


def password_fingerprint(user) -> str:
    """
    Short keyed digest of the user's stored password hash.

    Safe to embed in a signed (but readable) token: it reveals nothing about
    the password or its hash, and it changes whenever the password changes.
    """
    stored_hash = str(getattr(user, "_password", "") or "")
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, stored_hash.encode(), hashlib.sha256).hexdigest()[:32]


def fingerprint_matches(user, fingerprint) -> bool:
    if not isinstance(fingerprint, str):
        return False
    return hmac.compare_digest(password_fingerprint(user), fingerprint)


def issue_access_token(user) -> str:
    """Create an access token bound to the user's current password."""
    return create_access_token(
        identity=user.id,
        additional_claims={PASSWORD_CLAIM: password_fingerprint(user)},
    )


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _salt(purpose: str) -> str:
    return f"{current_app.config['SECURITY_PASSWORD_SALT']}:{purpose}"


def sign_token(payload, purpose: str) -> str:
    return _serializer().dumps(payload, salt=_salt(purpose))


def load_token(token: str, purpose: str, max_age: int = TOKEN_MAX_AGE_SECONDS):
    """Return the token payload, or None if it is invalid, expired or for another purpose."""
    try:
        return _serializer().loads(token, salt=_salt(purpose), max_age=max_age)
    except (BadSignature, SignatureExpired) as e:
        current_app.logger.info(f"Rejected {purpose} token: {type(e).__name__}")
        return None


def find_account(user_id):
    """Look up a consumer, merchant or administrator by ID."""
    from app import db
    from app.models import Administrator, Consumer, Merchant

    if not user_id:
        return None
    for model in (Consumer, Merchant, Administrator):
        user = db.session.get(model, user_id)
        if user is not None:
            return user
    return None


def is_access_token_revoked(jwt_header, jwt_payload) -> bool:
    """
    A token is revoked when its account no longer exists or its password has
    changed since the token was issued. Tokens issued before password binding
    carry no fingerprint and are treated as revoked.
    """
    user = find_account(jwt_payload.get("sub"))
    if user is None:
        return True
    return not fingerprint_matches(user, jwt_payload.get(PASSWORD_CLAIM))
