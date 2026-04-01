from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    Action,
    AllowList,
    BlockList,
    Detection,
    Feedback,
    Mailbox,
    Message,
    Tenant,
)


@admin.register(Tenant)
class TenantAdmin(ModelAdmin):
    list_display = ["name", "tenant_id", "is_active", "last_synced_at", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "tenant_id"]


@admin.register(Mailbox)
class MailboxAdmin(ModelAdmin):
    list_display = ["email", "display_name", "tenant", "is_vip", "is_active", "last_checked_at"]
    list_filter = ["is_active", "is_vip", "tenant"]
    search_fields = ["email", "display_name"]


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ["sender_email", "subject", "mailbox", "is_processed", "received_at"]
    list_filter = ["is_processed"]
    search_fields = ["sender_email", "subject"]


@admin.register(Detection)
class DetectionAdmin(ModelAdmin):
    list_display = ["message", "score", "verdict", "created_at"]
    list_filter = ["verdict"]
    search_fields = ["message__subject", "message__sender_email"]


@admin.register(Action)
class ActionAdmin(ModelAdmin):
    list_display = ["detection", "action_type", "status", "executed_at"]
    list_filter = ["action_type", "status"]


@admin.register(Feedback)
class FeedbackAdmin(ModelAdmin):
    list_display = ["detection", "user", "feedback_type", "created_at"]
    list_filter = ["feedback_type"]


@admin.register(AllowList)
class AllowListAdmin(ModelAdmin):
    list_display = ["domain", "tenant", "added_by", "created_at"]
    search_fields = ["domain"]


@admin.register(BlockList)
class BlockListAdmin(ModelAdmin):
    list_display = ["domain", "tenant", "added_by", "created_at"]
    search_fields = ["domain"]
