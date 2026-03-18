"""
SES Email Notifier

Sends notification emails when the self-heal pipeline generates new content.
Skips email in local dev (logs instead).
"""

import os
import logging
import boto3

logger = logging.getLogger(__name__)


def _get_ses_client():
    """Get SES client. Only used in production."""
    return boto3.client("ses", region_name=os.getenv("AWS_REGION", "us-east-1"))


def send_self_heal_email(bot_id: str, question: str, generated_content: str, to_email: str):
    """Send an email notification about auto-generated content.

    In local dev, logs the notification instead of sending email.
    """
    subject = f"[Bot Factory] Self-heal: new content for {bot_id}"
    body = (
        f"The self-healing knowledge base generated new content for bot '{bot_id}'.\n\n"
        f"Triggered by question:\n  {question}\n\n"
        f"Generated content:\n"
        f"{'=' * 60}\n"
        f"{generated_content}\n"
        f"{'=' * 60}\n\n"
        f"This content has been automatically embedded and is now live.\n"
        f"Please review for accuracy and edit or remove if needed.\n\n"
        f"S3 location: s3://bot-factory-data/bots/{bot_id}/data/\n"
    )

    if os.getenv("APP_ENV", "local") != "production":
        logger.info(f"[ses_notifier:{bot_id}] LOCAL MODE — would send email to {to_email}")
        logger.info(f"[ses_notifier:{bot_id}] Subject: {subject}")
        logger.info(f"[ses_notifier:{bot_id}] Body:\n{body}")
        return

    try:
        ses = _get_ses_client()
        ses.send_email(
            Source=os.getenv("SES_FROM_EMAIL", f"botfactory@{os.getenv('SES_DOMAIN', 'example.com')}"),
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        logger.info(f"[ses_notifier:{bot_id}] Email sent to {to_email}")
    except Exception as e:
        logger.error(f"[ses_notifier:{bot_id}] Failed to send email: {e}")
