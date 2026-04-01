import uuid

from django.conf import settings
from django.db import models

from apps.email_phishing_defender.services.encryption import decrypt_value, encrypt_value


# ── Tenant ──────────────────────────────────────────────────────────────────


class Tenant(models.Model):
    """Microsoft 365 tenant connected via admin consent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenants"
    )
    tenant_id = models.CharField(
        max_length=255, unique=True, help_text="Microsoft tenant ID"
    )
    name = models.CharField(max_length=255, blank=True)
    _access_token = models.TextField(blank=True, db_column="access_token")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def access_token(self):
        return decrypt_value(self._access_token)

    @access_token.setter
    def access_token(self, value):
        self._access_token = encrypt_value(value)

    def __str__(self):
        return self.name or self.tenant_id

    class Meta:
        ordering = ["-created_at"]


# ── Mailbox ─────────────────────────────────────────────────────────────────


class Mailbox(models.Model):
    """User mailbox within a Microsoft 365 tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="mailboxes"
    )
    email = models.EmailField()
    display_name = models.CharField(max_length=255, blank=True)
    ms_user_id = models.CharField(
        max_length=255, help_text="Microsoft Graph user ID"
    )
    is_vip = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email

    class Meta:
        unique_together = ["tenant", "email"]
        ordering = ["email"]


# ── Message ─────────────────────────────────────────────────────────────────


class Message(models.Model):
    """Normalised email message."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mailbox = models.ForeignKey(
        Mailbox, on_delete=models.CASCADE, related_name="messages"
    )
    ms_message_id = models.CharField(
        max_length=512, unique=True, help_text="Microsoft Graph message ID"
    )
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=255, blank=True)
    reply_to = models.EmailField(blank=True)
    subject = models.CharField(max_length=1024, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    received_at = models.DateTimeField()
    headers = models.JSONField(default=dict, blank=True)
    attachments_meta = models.JSONField(default=list, blank=True)
    is_processed = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_email}: {self.subject[:50]}"

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["ms_message_id"]),
            models.Index(fields=["mailbox", "received_at"]),
            models.Index(fields=["is_processed"]),
        ]


# ── MessageLink ─────────────────────────────────────────────────────────────


class MessageLink(models.Model):
    """Extracted link from a message."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="links"
    )
    url = models.URLField(max_length=2048)
    display_text = models.CharField(max_length=2048, blank=True)
    is_suspicious = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.url[:100]


# ── Detection ───────────────────────────────────────────────────────────────


class Detection(models.Model):
    """Phishing detection result for a message."""

    class Verdict(models.TextChoices):
        SAFE = "safe", "Safe"
        SUSPICIOUS = "suspicious", "Suspicious"
        PHISHING = "phishing", "Phishing"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.OneToOneField(
        Message, on_delete=models.CASCADE, related_name="detection"
    )
    score = models.IntegerField(default=0, help_text="Risk score 0–100")
    verdict = models.CharField(
        max_length=20, choices=Verdict.choices, default=Verdict.SAFE
    )
    reason_codes = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    rules_applied = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.verdict} ({self.score}) – {self.message.subject[:30]}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["verdict"]),
            models.Index(fields=["score"]),
        ]


# ── Action ──────────────────────────────────────────────────────────────────


class Action(models.Model):
    """Action taken on a detected phishing email."""

    class ActionType(models.TextChoices):
        QUARANTINE = "quarantine", "Quarantine"
        LABEL_SUSPICIOUS = "label_suspicious", "Label Suspicious"
        NO_ACTION = "no_action", "No Action"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    detection = models.ForeignKey(
        Detection, on_delete=models.CASCADE, related_name="actions"
    )
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} – {self.status}"


# ── Feedback ────────────────────────────────────────────────────────────────


class Feedback(models.Model):
    """User feedback on detection results."""

    class FeedbackType(models.TextChoices):
        FALSE_POSITIVE = "false_positive", "False Positive"
        FALSE_NEGATIVE = "false_negative", "False Negative"
        CONFIRMED = "confirmed", "Confirmed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    detection = models.ForeignKey(
        Detection, on_delete=models.CASCADE, related_name="feedbacks"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phishing_feedbacks",
    )
    feedback_type = models.CharField(max_length=20, choices=FeedbackType.choices)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedback_type} on {self.detection_id}"


# ── AllowList / BlockList ───────────────────────────────────────────────────


class AllowList(models.Model):
    """Allowed domains / senders that bypass detection."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="allow_list"
    )
    domain = models.CharField(max_length=255)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    reason = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.domain

    class Meta:
        unique_together = ["tenant", "domain"]


class BlockList(models.Model):
    """Blocked domains / senders that always flag as phishing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="block_list"
    )
    domain = models.CharField(max_length=255)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    reason = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.domain

    class Meta:
        unique_together = ["tenant", "domain"]
