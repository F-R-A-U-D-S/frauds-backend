import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def send_export_email(to_email: str, download_link: str, format: str):
    """
    Sends an email with the download link to the user using AWS SES.
    """
    subject = f"Your Fraud Analysis {format.upper()} Export is Ready"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e1e1e1; border-radius: 8px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #007bff; padding-bottom: 10px;">Fraud Analysis Export Complete</h2>
                <p>Hello,</p>
                <p>Your requested <strong>{format.upper()}</strong> export for the latest fraud analysis session has been successfully generated.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Security Notice:</strong> This download link is valid for <strong>30 minutes</strong>.</p>
                </div>

                <p>You can access your report using the secure link below:</p>
                
                <p style="word-break: break-all; margin: 20px 0;">
                    <a href="{download_link}" style="color: #007bff; text-decoration: underline;">{download_link}</a>
                </p>

                <p style="font-size: 0.9em; color: #666;">If you are unable to click the link, please copy and paste the URL above into your web browser.</p>
                <br>
                <hr style="border: 0; border-top: 1px solid #eee;">
                <p style="font-size: 0.8em; color: #888;">
                    Best regards,<br>
                    <strong>The F.R.A.U.D.S Security Team</strong>
                </p>
            </div>
        </body>
    </html>
    """

    # Check if AWS credentials are configured
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        logger.warning(f"AWS Credentials not configured. Mock sending email to {to_email} with link: {download_link}")
        return

    try:
        client = boto3.client(
            "ses",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

        response = client.send_email(
            Destination={
                "ToAddresses": [to_email],
            },
            Message={
                "Body": {
                    "Html": {
                        "Charset": "UTF-8",
                        "Data": html_content,
                    },
                    "Text": {
                        "Charset": "UTF-8",
                        "Data": f"Your {format.upper()} export is ready. Download it here: {download_link}",
                    },
                },
                "Subject": {
                    "Charset": "UTF-8",
                    "Data": subject,
                },
            },
            Source=settings.EMAILS_FROM_EMAIL,
        )
            
        logger.info(f"Email sent to {to_email} MessageId: {response['MessageId']}")

    except ClientError as e:
        logger.error(f"Failed to send email via SES: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
