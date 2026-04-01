"""
Celery tasks for the Email Phishing Defender.

Task chain:
  poll_all_mailboxes  (periodic)
    └─ fetch_new_emails  (per mailbox)
         └─ process_email
              └─ score_email
                   └─ apply_action
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Periodic entry-points ───────────────────────────────────────────────────


@shared_task
def poll_all_mailboxes():
    """Periodic: dispatch email-fetch jobs for every active mailbox."""
    from apps.email_phishing_defender.models import Mailbox

    mailboxes = Mailbox.objects.filter(is_active=True, tenant__is_active=True)
    for mb in mailboxes:
        fetch_new_emails.delay(str(mb.id))
    logger.info("Dispatched email-fetch for %d mailbox(es)", mailboxes.count())


@shared_task
def sync_all_tenants():
    """Periodic: sync mailboxes for all active tenants."""
    from apps.email_phishing_defender.models import Tenant

    tenants = Tenant.objects.filter(is_active=True)
    for t in tenants:
        sync_mailboxes.delay(str(t.id))
    logger.info("Dispatched mailbox-sync for %d tenant(s)", tenants.count())


# ── Core tasks ──────────────────────────────────────────────────────────────


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_mailboxes(self, tenant_id):
    """Fetch all users from a tenant via Graph API and upsert mailboxes."""
    from apps.email_phishing_defender.models import Mailbox, Tenant
    from apps.email_phishing_defender.services.microsoft_graph import MicrosoftGraphService

    try:
        tenant = Tenant.objects.get(id=tenant_id, is_active=True)
        graph = MicrosoftGraphService(tenant)
        users = graph.fetch_users()

        for user in users:
            email = user.get("mail") or user.get("userPrincipalName", "")
            if not email or "@" not in email:
                continue
            Mailbox.objects.update_or_create(
                tenant=tenant,
                ms_user_id=user["id"],
                defaults={
                    "email": email,
                    "display_name": user.get("displayName", ""),
                    "is_active": True,
                },
            )

        tenant.last_synced_at = timezone.now()
        tenant.save(update_fields=["last_synced_at"])
        logger.info("Synced %d user(s) for tenant %s", len(users), tenant_id)
    except Exception as exc:
        logger.error("sync_mailboxes failed for tenant %s: %s", tenant_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_new_emails(self, mailbox_id):
    """Fetch new emails for one mailbox and kick off processing."""
    from apps.email_phishing_defender.models import Mailbox, Message, MessageLink
    from apps.email_phishing_defender.services.email_normalizer import normalize_email
    from apps.email_phishing_defender.services.microsoft_graph import MicrosoftGraphService

    try:
        mailbox = Mailbox.objects.select_related("tenant").get(
            id=mailbox_id, is_active=True
        )
        graph = MicrosoftGraphService(mailbox.tenant)
        raw_messages = graph.fetch_messages(mailbox.ms_user_id, since=mailbox.last_checked_at)

        created = 0
        for raw in raw_messages:
            ms_id = raw.get("id", "")
            if Message.objects.filter(ms_message_id=ms_id).exists():
                continue

            attachments = []
            if raw.get("hasAttachments"):
                try:
                    attachments = graph.fetch_message_attachments(mailbox.ms_user_id, ms_id)
                except Exception as e:
                    logger.warning("Attachment fetch failed for %s: %s", ms_id, e)

            norm = normalize_email(raw, attachments)

            message = Message.objects.create(
                mailbox=mailbox,
                ms_message_id=norm["ms_message_id"],
                sender_email=norm["sender_email"],
                sender_name=norm["sender_name"],
                reply_to=norm["reply_to"],
                subject=norm["subject"],
                body_text=norm["body_text"],
                body_html=norm["body_html"],
                received_at=norm["received_at"],
                headers=norm["headers"],
                attachments_meta=norm["attachments_meta"],
                metadata={
                    "to_recipients": norm["to_recipients"],
                    "cc_recipients": norm["cc_recipients"],
                    "extracted_links": norm["extracted_links"],
                },
            )

            for link in norm["extracted_links"]:
                MessageLink.objects.create(
                    message=message,
                    url=link["url"],
                    display_text=link.get("display_text", ""),
                )

            process_email.delay(str(message.id))
            created += 1

        mailbox.last_checked_at = timezone.now()
        mailbox.save(update_fields=["last_checked_at"])
        logger.info("Fetched %d new email(s) for %s", created, mailbox.email)
    except Exception as exc:
        logger.error("fetch_new_emails failed for %s: %s", mailbox_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_email(self, message_id):
    """Normalisation is already done during fetch; hand off to scoring."""
    from apps.email_phishing_defender.models import Message

    try:
        message = Message.objects.get(id=message_id)
        if message.is_processed:
            return
        score_email.delay(str(message.id))
    except Message.DoesNotExist:
        logger.error("Message %s not found", message_id)
    except Exception as exc:
        logger.error("process_email failed for %s: %s", message_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def score_email(self, message_id):
    """Run the phishing-detection rule engine against a message."""
    from apps.email_phishing_defender.models import (
        AllowList,
        BlockList,
        Detection,
        Mailbox,
        Message,
    )
    from apps.email_phishing_defender.services.phishing_detector import PhishingDetector

    try:
        message = Message.objects.select_related("mailbox__tenant").get(id=message_id)

        if Detection.objects.filter(message=message).exists():
            return

        tenant = message.mailbox.tenant
        allow = list(AllowList.objects.filter(tenant=tenant).values_list("domain", flat=True))
        block = list(BlockList.objects.filter(tenant=tenant).values_list("domain", flat=True))
        vips = list(
            Mailbox.objects.filter(tenant=tenant, is_vip=True).values_list("email", flat=True)
        )

        email_data = {
            "sender_email": message.sender_email,
            "sender_name": message.sender_name,
            "reply_to": message.reply_to,
            "subject": message.subject,
            "body_text": message.body_text,
            "body_html": message.body_html,
            "extracted_links": message.metadata.get("extracted_links", []),
            "attachments_meta": message.attachments_meta,
            "headers": message.headers,
            "to_recipients": message.metadata.get("to_recipients", []),
            "cc_recipients": message.metadata.get("cc_recipients", []),
        }

        detector = PhishingDetector(allow_list=allow, block_list=block, vip_emails=vips)
        result = detector.analyze(email_data)

        detection = Detection.objects.create(
            message=message,
            score=result["score"],
            verdict=result["verdict"],
            reason_codes=result["reason_codes"],
            evidence=result["evidence"],
            rules_applied=result["rules_applied"],
        )

        message.is_processed = True
        message.save(update_fields=["is_processed"])

        apply_action.delay(str(detection.id))
        logger.info("Scored message %s: %s (%s)", message_id, result["verdict"], result["score"])
    except Exception as exc:
        logger.error("score_email failed for %s: %s", message_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def apply_action(self, detection_id):
    """Execute the appropriate Graph API action for a detection."""
    from apps.email_phishing_defender.models import Detection
    from apps.email_phishing_defender.services.action_engine import ActionEngine
    from apps.email_phishing_defender.services.microsoft_graph import MicrosoftGraphService

    try:
        detection = Detection.objects.select_related(
            "message__mailbox__tenant"
        ).get(id=detection_id)

        mailbox = detection.message.mailbox
        graph = MicrosoftGraphService(mailbox.tenant)
        engine = ActionEngine(graph)
        action = engine.execute(detection, mailbox)

        logger.info(
            "Action %s (%s) for detection %s",
            action.action_type,
            action.status,
            detection_id,
        )
    except Exception as exc:
        logger.error("apply_action failed for %s: %s", detection_id, exc)
        raise self.retry(exc=exc)
