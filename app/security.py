"""
Checks on the signing secrets the application needs at startup.
"""

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
