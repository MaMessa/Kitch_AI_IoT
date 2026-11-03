# Import the standard email builder for local development delivery.
from email.message import EmailMessage  # Build multipart messages that Mailpit can display.
# Import HTML escaping for safe links and email labels.
from html import escape  # Prevent values from being interpreted as unintended markup.
# Import environment settings and local SMTP delivery.
import os  # Read delivery mode and mail service configuration.
import smtplib  # Send development messages to Mailpit over local SMTP.
# Import URL encoding for one-time action tokens.
from urllib.parse import quote  # Safely place a token in a link query parameter.
# Import the Resend SDK and errors for real transactional delivery.
import resend  # Send real transactional email through Resend.
from requests.exceptions import RequestException  # Catch HTTP transport failures from the SDK.
from resend.exceptions import ResendError  # Catch API rejections from Resend.


# Represent any delivery configuration or provider failure at the API boundary.
class EmailDeliveryError(Exception):  # Keep provider details out of public API responses.
    pass  # Use the shared exception type for both delivery backends.


# Send verification and reset links through local Mailpit or the Resend API.
def send_account_action_email(recipient: str, subject: str, token: str, frontend_path: str, action_label: str) -> None:  # Share email formatting across account actions.
    email_backend = os.getenv("EMAIL_BACKEND", "resend").strip().lower()  # Choose local capture or real sending explicitly.
    frontend_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")  # Build the link for the current front-end environment.
    action_url = f"{frontend_url}/{frontend_path}?token={quote(token)}"  # Put the one-time token in the action URL.
    safe_action_url = escape(action_url, quote=True)  # Escape the URL before inserting it into HTML.
    safe_action_label = escape(action_label)  # Escape visible action text before inserting it into HTML.
    plain_text = f"{action_label}: {action_url}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez cet email."  # Provide a readable text alternative.
    html_content = f"<p>Bonjour,</p><p>Pour {safe_action_label.lower()}, utilisez ce lien :</p><p><a href=\"{safe_action_url}\">{safe_action_label}</a></p><p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>"  # Create a minimal email layout that works in common clients.
    if email_backend == "mailpit":  # Capture emails locally during development.
        if os.getenv("APP_ENV", "").strip().lower() != "development":  # Require an explicit development environment before using a fake sender.
            raise EmailDeliveryError("Mailpit ne peut être utilisé qu'avec APP_ENV=development.")  # Prevent accidental fake delivery outside development.
        sender = os.getenv("EMAIL_FROM_ADDRESS", "KitchAI <no-reply@kitchai.local>").strip()  # Use a clearly local sender identity.
        message = EmailMessage()  # Create a standards-compliant email message.
        message["From"] = sender  # Set the sender shown in the local inbox.
        message["To"] = recipient  # Keep the requested account email as the captured recipient.
        message["Subject"] = subject  # Identify whether this is verification or password recovery.
        message.set_content(plain_text)  # Add the plain-text version for basic email clients.
        message.add_alternative(html_content, subtype="html")  # Add the formatted version displayed by Mailpit.
        smtp_host = os.getenv("SMTP_HOST", "127.0.0.1").strip()  # Read the local Mailpit SMTP host.
        smtp_port = int(os.getenv("SMTP_PORT", "1025"))  # Read Mailpit's default SMTP port.
        try:  # Turn local SMTP errors into a clear application-level failure.
            with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as smtp_client:  # Connect to the local-only capture service.
                smtp_client.send_message(message)  # Store the message in Mailpit instead of delivering externally.
        except (OSError, smtplib.SMTPException) as error:  # Handle a stopped container or local connection failure.
            raise EmailDeliveryError("Mailpit est arrêté ou inaccessible sur le port SMTP configuré.") from error  # Tell the developer how to restore local delivery.
        return  # Do not continue to the Resend branch after local capture.
    if email_backend != "resend":  # Reject misspelled or unsupported configuration values.
        raise EmailDeliveryError("EMAIL_BACKEND doit être 'mailpit' ou 'resend'.")  # Prevent silent fallback to a different sender.
    api_key = os.getenv("RESEND_API_KEY", "").strip()  # Read the private key only when real delivery is selected.
    sender = os.getenv("RESEND_FROM_EMAIL", "").strip()  # Read the sender address authorized by Resend.
    if not api_key or not sender:  # Require credentials and a sender for real provider delivery.
        raise EmailDeliveryError("RESEND_API_KEY et RESEND_FROM_EMAIL sont requis pour Resend.")  # Never claim an email was delivered without configuration.
    resend.api_key = api_key  # Configure the SDK with the secret kept in the environment.
    try:  # Send the formatted message using the selected real provider.
        resend.Emails.send({"from": sender, "to": [recipient], "subject": subject, "html": html_content, "text": plain_text})  # Deliver both HTML and text versions through Resend.
    except ResendError as error:  # Catch API responses that reject the message.
        raise EmailDeliveryError("Resend n'a pas accepté l'email.") from error  # Keep provider details in server logs, not API responses.
    except RequestException as error:  # Catch timeouts and connection failures.
        raise EmailDeliveryError("Resend est momentanément injoignable.") from error  # Return a stable temporary-delivery error.
