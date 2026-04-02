from django.urls import path

from .views import (
    AllowListView,
    BlockListView,
    ConnectM365View,
    DashboardView,
    DetectionDetailView,
    DetectionListView,
    FeedbackReportView,
    M365CallbackView,
    MailboxListView,
    TenantListView,
    TenantResyncView,
    TenantStatusView,
    TestAnalyzeEmailView,
)

urlpatterns = [
    # M365 connection
    path("phishing/connect/m365/", ConnectM365View.as_view(), name="connect-m365"),
    path("phishing/connect/m365/callback/", M365CallbackView.as_view(), name="m365-callback"),

    # Tenants / Connection status
    path("phishing/tenants/", TenantListView.as_view(), name="tenant-list"),
    path("phishing/tenants/status/", TenantStatusView.as_view(), name="tenant-status"),
    path("phishing/tenants/<uuid:tenant_id>/resync/", TenantResyncView.as_view(), name="tenant-resync"),

    # Mailboxes
    path("phishing/mailboxes/", MailboxListView.as_view(), name="mailbox-list"),

    # Detections
    path("phishing/detections/", DetectionListView.as_view(), name="detection-list"),
    path("phishing/detections/<uuid:pk>/", DetectionDetailView.as_view(), name="detection-detail"),

    # Allow / Block lists
    path("phishing/allowlist/domain/", AllowListView.as_view(), name="allowlist"),
    path("phishing/blocklist/domain/", BlockListView.as_view(), name="blocklist"),

    # Feedback
    path("phishing/feedback/report/", FeedbackReportView.as_view(), name="feedback-report"),

    # Dashboard
    path("phishing/dashboard/", DashboardView.as_view(), name="phishing-dashboard"),

    # Test / Demo (Postman)
    path("phishing/test/analyze/", TestAnalyzeEmailView.as_view(), name="test-analyze"),
]
