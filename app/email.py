from threading import Thread
from datetime import datetime
import time

from flask import current_app, render_template
from mailtrap import Mail, Address, MailtrapClient
from requests.exceptions import RequestException, SSLError, ConnectionError

from app.security import (
    EMAIL_CONFIRMATION,
    PASSWORD_RESET,
    TOKEN_MAX_AGE_SECONDS,
    find_account,
    fingerprint_matches,
    load_token,
    password_fingerprint,
    sign_token,
)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1  # Base delay in seconds (will be multiplied exponentially)


def generate_confirmation_token(email):
    """
    Generate a token that confirms ownership of an email address.

    It is only accepted by confirm_token and cannot be used to reset a password.

    :param email: str - The email address to generate a token for
    :return: str - The generated token
    """
    return sign_token(email, EMAIL_CONFIRMATION)


def confirm_token(token, expiration=TOKEN_MAX_AGE_SECONDS):
    """
    Confirm an email verification token.

    :param token: str - The token to confirm
    :param expiration: int - The maximum age of the token in seconds
    :return: str or None - The email address if valid, None otherwise
    """
    email = load_token(token, EMAIL_CONFIRMATION, max_age=expiration)
    return email if isinstance(email, str) else None


def generate_password_reset_token(user):
    """
    Generate a password-reset token for a consumer or merchant.

    The token is bound to the account's current password, so it stops working
    once the password has been changed (including by using this token).

    :param user: Consumer | Merchant - The account to reset
    :return: str - The generated token
    """
    return sign_token(
        {"id": user.id, "pwd": password_fingerprint(user)}, PASSWORD_RESET
    )


def verify_password_reset_token(token, expiration=TOKEN_MAX_AGE_SECONDS):
    """
    Return the account a password-reset token belongs to, or None if the token
    is invalid, expired, issued for another purpose or already used.

    :param token: str - The token to verify
    :param expiration: int - The maximum age of the token in seconds
    :return: Consumer | Merchant | None
    """
    payload = load_token(token, PASSWORD_RESET, max_age=expiration)
    if not isinstance(payload, dict):
        return None
    from app.models import Consumer, Merchant

    user = find_account(payload.get("id"))
    if not isinstance(user, (Consumer, Merchant)):
        return None
    if not fingerprint_matches(user, payload.get("pwd")):
        return None
    return user


def get_mailtrap_client():
    """
    Get the Mailtrap client instance.

    :return: MailtrapClient - The Mailtrap client
    """
    api_token = current_app.config.get('MAILTRAP_API_TOKEN')
    if not api_token:
        raise ValueError("MAILTRAP_API_TOKEN is not configured")
    return MailtrapClient(token=api_token)


def send_with_retry(client, mail_message, app):
    """
    Send an email with retry logic and exponential backoff.
    
    :param client: MailtrapClient - The Mailtrap client instance
    :param mail_message: Mail - The Mailtrap Mail object
    :param app: Flask - The Flask app object for logging
    :return: tuple - (success: bool, response: any)
    """
    last_exception = None
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.send(mail_message)
            return True, response
        except (SSLError, ConnectionError, RequestException) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                app.logger.warning(
                    f"Email send attempt {attempt + 1}/{MAX_RETRIES} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                app.logger.error(
                    f"Email send failed after {MAX_RETRIES} attempts: {e}"
                )
        except Exception as e:
            # Non-retryable error
            app.logger.error(f"Failed to send email via Mailtrap: {e}")
            return False, None
    
    return False, last_exception


def send_async_email(app, mail_message):
    """
    Asynchronously sends an email using Mailtrap SDK within the given Flask
        app context. Includes retry logic for transient network errors.

    :param app: Flask - The Flask app object
    :param mail_message: Mail - The Mailtrap Mail object containing email details
    """
    with app.app_context():
        if app.config.get('TESTING'):
            # In testing mode, log the email instead of sending it
            app.logger.info(
                f"[TEST MODE] Email would be sent to: {mail_message.to}")
            return True

        try:
            client = get_mailtrap_client()
            success, response = send_with_retry(client, mail_message, app)
            if success:
                app.logger.info(f"Email sent successfully: {response}")
            return success
        except Exception as e:
            app.logger.error(f"Failed to send email via Mailtrap: {e}")
            return False


def send_email(to, subject, template, **kwargs):
    """
    Asynchronously sends an email using Mailtrap SDK with support for HTML templates.

    :param to: list - A list of email recipients
    :param subject: str - Email subject
    :param template: str - Base name of the email template (without the file
        extension)
    :param kwargs: dict - Additional keyword arguments to pass to the email
        templates

    :return thread: Thread - Represents the asynchronous email sending process
    """
    app = current_app._get_current_object()

    # Get configuration values for template context
    template_context = {
        'app_name': app.config.get('APP_NAME', 'StudentX'),
        'frontend_url': app.config.get('FRONTEND_URL', 'https://studentx.co.ke'),
        'backend_url': app.config.get('BACKEND_URL', 'https://api.studentx.co.ke'),
        'current_year': datetime.now().year,
        **kwargs
    }

    # Render the HTML template
    rendered_html = render_template(template + '.html', **template_context)

    # Get sender configuration
    sender_email = app.config.get(
        'MAIL_DEFAULT_SENDER_EMAIL', 'info@studentx.co.ke')
    sender_name = app.config.get('MAIL_DEFAULT_SENDER_NAME', 'StudentX')

    # Build recipient list
    recipients = [Address(email=email) for email in to]

    # Create Mailtrap Mail object
    mail_message = Mail(
        sender=Address(email=sender_email, name=sender_name),
        to=recipients,
        subject=subject,
        html=rendered_html,
        category=app.config.get('APP_NAME', 'StudentX')
    )

    thread = Thread(target=send_async_email, args=[app, mail_message])
    thread.start()

    return thread


def send_email_sync(to, subject, template, **kwargs):
    """
    Synchronously sends an email using Mailtrap SDK with support for HTML templates.
    Use this when you need to wait for the email to be sent and get the result.

    :param to: list - A list of email recipients
    :param subject: str - Email subject
    :param template: str - Base name of the email template (without the file
        extension)
    :param kwargs: dict - Additional keyword arguments to pass to the email
        templates

    :return: bool - True if email was sent successfully, False otherwise
    """
    app = current_app._get_current_object()

    if app.config.get('TESTING'):
        app.logger.info(f"[TEST MODE] Email would be sent to: {to}")
        return True

    # Get configuration values for template context
    template_context = {
        'app_name': app.config.get('APP_NAME', 'StudentX'),
        'frontend_url': app.config.get('FRONTEND_URL', 'https://studentx.co.ke'),
        'backend_url': app.config.get('BACKEND_URL', 'https://api.studentx.co.ke'),
        'current_year': datetime.now().year,
        **kwargs
    }

    # Render the HTML template
    rendered_html = render_template(template + '.html', **template_context)

    # Get sender configuration
    sender_email = app.config.get(
        'MAIL_DEFAULT_SENDER_EMAIL', 'info@studentx.co.ke')
    sender_name = app.config.get('MAIL_DEFAULT_SENDER_NAME', 'StudentX')

    # Build recipient list
    recipients = [Address(email=email) for email in to]

    # Create Mailtrap Mail object
    mail_message = Mail(
        sender=Address(email=sender_email, name=sender_name),
        to=recipients,
        subject=subject,
        html=rendered_html,
        category=app.config.get('APP_NAME', 'StudentX')
    )

    try:
        client = get_mailtrap_client()
        success, response = send_with_retry(client, mail_message, current_app._get_current_object())
        if success:
            app.logger.info(f"Email sent successfully: {response}")
        return success
    except Exception as e:
        app.logger.error(f"Failed to send email via Mailtrap: {e}")
        return False
