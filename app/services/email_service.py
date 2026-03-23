import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def send_export_email(to_email: str, download_link: str, format: str):
    subject = f"Your FRAUDS {format.upper()} report is ready"

    requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    text_content = f"""Hello,

Your requested {format.upper()} report from FRAUDS is ready.

Requested at: {requested_at}
Download link: {download_link}

This link will expire in 30 minutes.

If you did not request this report, you can ignore this email.

FRAUDS
fraudsapp.online
support@fraudsapp.online
"""

    html_content = f"""
    <html>
        <body style="margin:0; padding:0; font-family: Arial, sans-serif; color:#222; background-color:#f6f7f9;">
            <div style="max-width:600px; margin:40px auto; background:#ffffff; border:1px solid #5d19c4; border-radius:10px; overflow:hidden;">
                <div style="padding:24px 24px 12px 24px;">
                    <h2 style="margin:0 0 16px 0; font-size:24px; color:#111827;">Your {format.upper()} report is ready</h2>
                    <p style="margin:0 0 16px 0;">Hello,</p>
                    <p style="margin:0 0 16px 0;">
                        Your requested <strong>{format.upper()}</strong> report from <strong>FRAUDS</strong> has been generated successfully.
                    </p>
                    <p style="margin:0 0 16px 0;">
                        <strong>Requested at:</strong> {requested_at}
                    </p>
                    <p style="margin:0 0 20px 0;">
                        This download link will expire in <strong>30 minutes</strong>.
                    </p>
                    <p style="margin:0 0 24px 0;">
                        <a href="{download_link}" style="display:inline-block; padding:12px 20px; background:#2563eb; color:#ffffff; text-decoration:none; border-radius:6px; font-weight:bold;">
                            Download report
                        </a>
                    </p>
                    <p style="margin:0 0 12px 0; font-size:14px; color:#5d19c4;">
                        If the button does not work, copy and paste this link into your browser:
                    </p>
                    <p style="margin:0 0 20px 0; font-size:14px; color:#5d19c4; word-break:break-all;">
                        {download_link}
                    </p>
                    <p style="margin:0 0 16px 0; font-size:14px; color:#5d19c4;">
                        If you did not request this report, you can ignore this email.
                    </p>
                </div>
                <div style="padding:16px 24px; border-top:1px solid #e5e7eb; font-size:13px; color:#6b7280;">
                    FRAUDS<br>
                    fraudsapp.online<br>
                    support@fraudsapp.online
                </div>
            </div>
        </body>
    </html>
    """

    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        logger.warning(f"AWS credentials not configured. Mock sending email to {to_email} with link: {download_link}")
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
                        "Data": text_content,
                    },
                },
                "Subject": {
                    "Charset": "UTF-8",
                    "Data": subject,
                },
            },
            Source=settings.EMAILS_FROM_EMAIL,
            ReplyToAddresses=["support@fraudsapp.online"],
        )

        logger.info(f"Email sent to {to_email} MessageId: {response['MessageId']}")

    except ClientError as e:
        logger.error(f"Failed to send email via SES: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")