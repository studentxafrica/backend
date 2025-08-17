from threading import Thread


from flask import current_app, render_template
from flask_mailman import EmailMultiAlternatives  # type: ignore
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])


def confirm_token(token, expiration=3600):
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


def send_async_email(app, message):
    """
    Asynchronously sends an email using Flask-Mailman within the given Flask
        app context.

    :param app: Flask - The Flask app object
    :param msg: Message - The Message object containing email details
    """
    with app.app_context():
        if app.config['TESTING']:
            # In testing mode, log the email instead of sending it
            pass
        else:
            message.send()


def send_email(to, subject, template, **kwargs):
    """
    Asynchronously sends an email using Flask-Mailman with support for plain
        text and HTML templates.

    :param to: list - A list of email recipients
    :param subject: str - Email subject
    :param template: str - Base name of the email template (without the file
        extension)
    :param kwargs: dict - Additional keyword arguments to pass to the email
        templates

    :return thread: Thread - Represents the asynchronous email sending process
    """
    app = current_app._get_current_object()

    rendered_body = render_template(template + '.html', **kwargs)
    rendered_html = render_template(template + '.html', **kwargs)

    message = EmailMultiAlternatives(subject=subject, body=rendered_body,
                                     to=to)
    message.attach_alternative(rendered_html, 'text/html')

    thread = Thread(target=send_async_email, args=[app, message])
    thread.start()

    return thread
