from threading import Thread
from datetime import datetime

from flask import current_app, render_template
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from mailtrap import Mail, Address, MailtrapClient


def generate_confirmation_token(email):
    """
    Generate a confirmation token for email verification.

    :param email: str - The email address to generate a token for
    :return: str - The generated token
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])


def confirm_token(token, expiration=3600):
    """
    Confirm an email verification token.

    :param token: str - The token to confirm
    :param expiration: int - The maximum age of the token in seconds
    :return: str or None - The email address if valid, None otherwise
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration,
        )
        return email
    except (BadSignature, SignatureExpired) as e:
        current_app.logger.error(f'Email token confirmation error: {e}')
        return None


def get_mailtrap_client():
    """
    Get the Mailtrap client instance.

    :return: MailtrapClient - The Mailtrap client
    """
    api_token = current_app.config.get('MAILTRAP_API_TOKEN')
    if not api_token:
        raise ValueError("MAILTRAP_API_TOKEN is not configured")
    return MailtrapClient(token=api_token)


def send_async_email(app, mail_message):
    """
    Asynchronously sends an email using Mailtrap SDK within the given Flask
        app context.

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
            response = client.send(mail_message)
            app.logger.info(f"Email sent successfully: {response}")
            return True
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
        response = client.send(mail_message)
        app.logger.info(f"Email sent successfully: {response}")
        return True
    except Exception as e:
        app.logger.error(f"Failed to send email via Mailtrap: {e}")
        return False
