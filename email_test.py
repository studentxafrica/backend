"""
Test script for Mailtrap email service.
Replace the API token with your actual Mailtrap API token.
"""
from mailtrap import Mail, Address, MailtrapClient

# Replace with your actual Mailtrap API token
MAILTRAP_API_TOKEN = "your_mailtrap_api_token_here"

sender = Address(email="info@studentx.co.ke", name="StudentX")
receiver = Address(email="kiruiallan003@gmail.com", name="A Test User")

mail = Mail(
    sender=sender,
    to=[receiver],
    subject="Hi Mailtrap - SDK Test",
    html="<h1>Hello!</h1><p>This is a test e-mail message sent via Mailtrap SDK.</p>",
    text="Hello! This is a test e-mail message sent via Mailtrap SDK.",
    category="Test"
)

client = MailtrapClient(token=MAILTRAP_API_TOKEN)
response = client.send(mail)
print(f"Email sent successfully: {response}")