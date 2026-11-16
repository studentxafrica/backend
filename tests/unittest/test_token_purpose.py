import pytest

pytestmark = pytest.mark.unittest


def test_tokens_are_bound_to_their_purpose(app):
    from app.security import EMAIL_CONFIRMATION, PASSWORD_RESET, load_token, sign_token

    with app.test_request_context():
        confirmation = sign_token("amina@example.com", EMAIL_CONFIRMATION)
        reset = sign_token("amina@example.com", PASSWORD_RESET)

        assert load_token(confirmation, EMAIL_CONFIRMATION) == "amina@example.com"
        assert load_token(confirmation, PASSWORD_RESET) is None
        assert load_token(reset, EMAIL_CONFIRMATION) is None
