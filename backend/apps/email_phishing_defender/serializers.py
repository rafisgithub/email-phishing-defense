from rest_framework import serializers

from .models import (
    Action,
    AllowList,
    BlockList,
    Detection,
    Feedback,
    Mailbox,
    Tenant,
)


# ── Tenant ──────────────────────────────────────────────────────────────────


class TenantSerializer(serializers.ModelSerializer):
    mailbox_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id", "tenant_id", "name", "is_active",
            "last_synced_at", "mailbox_count", "created_at",
        ]

    def get_mailbox_count(self, obj):
        return obj.mailboxes.count()


# ── Mailbox ─────────────────────────────────────────────────────────────────


class MailboxSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    message_count = serializers.SerializerMethodField()
    threat_count = serializers.SerializerMethodField()

    class Meta:
        model = Mailbox
        fields = [
            "id", "email", "display_name", "is_vip", "is_active",
            "last_checked_at", "tenant_name", "message_count",
            "threat_count", "created_at",
        ]

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_threat_count(self, obj):
        return Detection.objects.filter(
            message__mailbox=obj,
            verdict__in=["suspicious", "phishing"],
        ).count()


# ── Detection ───────────────────────────────────────────────────────────────


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = [
            "id", "action_type", "status", "error_message",
            "retry_count", "executed_at", "created_at",
        ]


class DetectionListSerializer(serializers.ModelSerializer):
    sender_email = serializers.CharField(source="message.sender_email")
    sender_name = serializers.CharField(source="message.sender_name")
    subject = serializers.CharField(source="message.subject")
    mailbox_email = serializers.CharField(source="message.mailbox.email")
    received_at = serializers.DateTimeField(source="message.received_at")

    class Meta:
        model = Detection
        fields = [
            "id", "score", "verdict", "reason_codes",
            "sender_email", "sender_name", "subject",
            "mailbox_email", "received_at", "created_at",
        ]


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "feedback_type", "comment", "created_at"]


class DetectionDetailSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    links = serializers.SerializerMethodField()
    actions = ActionSerializer(many=True, read_only=True)
    feedbacks = serializers.SerializerMethodField()

    class Meta:
        model = Detection
        fields = [
            "id", "score", "verdict", "reason_codes", "evidence",
            "rules_applied", "message", "links", "actions",
            "feedbacks", "created_at",
        ]

    def get_message(self, obj):
        msg = obj.message
        return {
            "id": str(msg.id),
            "sender_email": msg.sender_email,
            "sender_name": msg.sender_name,
            "reply_to": msg.reply_to,
            "subject": msg.subject,
            "body_text": msg.body_text[:2000],
            "received_at": msg.received_at,
            "mailbox": msg.mailbox.email,
            "attachments_meta": msg.attachments_meta,
            "headers": msg.headers,
        }

    def get_links(self, obj):
        from .models import MessageLink

        links = MessageLink.objects.filter(message=obj.message)
        return [
            {"id": str(l.id), "url": l.url, "display_text": l.display_text, "is_suspicious": l.is_suspicious}
            for l in links
        ]

    def get_feedbacks(self, obj):
        return FeedbackSerializer(obj.feedbacks.all(), many=True).data


# ── Feedback (create) ──────────────────────────────────────────────────────


class FeedbackCreateSerializer(serializers.ModelSerializer):
    detection_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Feedback
        fields = ["detection_id", "feedback_type", "comment"]

    def validate_detection_id(self, value):
        if not Detection.objects.filter(id=value).exists():
            raise serializers.ValidationError("Detection not found.")
        return value

    def create(self, validated_data):
        detection = Detection.objects.get(id=validated_data.pop("detection_id"))
        return Feedback.objects.create(
            detection=detection,
            user=self.context["request"].user,
            **validated_data,
        )


# ── AllowList / BlockList ──────────────────────────────────────────────────


class AllowListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllowList
        fields = ["id", "domain", "reason", "created_at"]


class BlockListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockList
        fields = ["id", "domain", "reason", "created_at"]


class DomainInputSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=255)
    reason = serializers.CharField(max_length=512, required=False, default="")


# ── Connect M365 ───────────────────────────────────────────────────────────


class ConnectM365Serializer(serializers.Serializer):
    redirect_uri = serializers.URLField()


class M365CallbackSerializer(serializers.Serializer):
    tenant_id = serializers.CharField(max_length=255)
    admin_consent = serializers.BooleanField()
