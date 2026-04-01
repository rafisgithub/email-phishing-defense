import uuid
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.utils.helpers import error, success

from .models import (
    AllowList,
    BlockList,
    Detection,
    Mailbox,
    Message,
    Tenant,
)
from .serializers import (
    AllowListSerializer,
    BlockListSerializer,
    ConnectM365Serializer,
    DetectionDetailSerializer,
    DetectionListSerializer,
    DomainInputSerializer,
    FeedbackCreateSerializer,
    MailboxSerializer,
    M365CallbackSerializer,
    TenantSerializer,
)
from .tasks import sync_mailboxes


# ── M365 Connection ─────────────────────────────────────────────────────────


class ConnectM365View(APIView):
    """Generate the Microsoft 365 admin-consent URL."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConnectM365Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        redirect_uri = serializer.validated_data["redirect_uri"]
        state = str(uuid.uuid4())

        consent_url = (
            f"https://login.microsoftonline.com/common/adminconsent"
            f"?client_id={settings.MS_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )
        return success(
            data={"consent_url": consent_url, "state": state},
            message="Admin consent URL generated.",
        )


class M365CallbackView(APIView):
    """Handle the Microsoft 365 admin-consent callback."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = M365CallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_ms_id = serializer.validated_data["tenant_id"]
        admin_consent = serializer.validated_data["admin_consent"]

        if not admin_consent:
            return error(
                message="Admin consent was not granted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        tenant, created = Tenant.objects.update_or_create(
            tenant_id=tenant_ms_id,
            defaults={"user": request.user, "is_active": True},
        )

        sync_mailboxes.delay(str(tenant.id))

        return success(
            data=TenantSerializer(tenant).data,
            message="Microsoft 365 tenant connected. Syncing mailboxes…",
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ── Mailboxes ───────────────────────────────────────────────────────────────


class MailboxListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenants = Tenant.objects.filter(user=request.user, is_active=True)
        qs = Mailbox.objects.filter(tenant__in=tenants).select_related("tenant")

        search = request.query_params.get("search", "")
        if search:
            qs = qs.filter(Q(email__icontains=search) | Q(display_name__icontains=search))

        return success(data=MailboxSerializer(qs, many=True).data, message="Mailboxes retrieved.")


# ── Detections ──────────────────────────────────────────────────────────────


class DetectionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenants = Tenant.objects.filter(user=request.user, is_active=True)
        qs = Detection.objects.filter(
            message__mailbox__tenant__in=tenants
        ).select_related("message__mailbox")

        verdict = request.query_params.get("verdict", "")
        if verdict:
            qs = qs.filter(verdict=verdict)

        search = request.query_params.get("search", "")
        if search:
            qs = qs.filter(
                Q(message__subject__icontains=search)
                | Q(message__sender_email__icontains=search)
            )

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (ValueError, TypeError):
            page = 1
        try:
            per_page = min(max(int(request.query_params.get("per_page", 20)), 1), 100)
        except (ValueError, TypeError):
            per_page = 20

        total = qs.count()
        offset = (page - 1) * per_page
        results = qs[offset : offset + per_page]

        return success(
            data={
                "results": DetectionListSerializer(results, many=True).data,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            },
            message="Detections retrieved.",
        )


class DetectionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        tenants = Tenant.objects.filter(user=request.user, is_active=True)
        try:
            detection = Detection.objects.select_related(
                "message__mailbox__tenant"
            ).get(id=pk, message__mailbox__tenant__in=tenants)
        except Detection.DoesNotExist:
            return error(message="Detection not found.", status_code=status.HTTP_404_NOT_FOUND)

        return success(
            data=DetectionDetailSerializer(detection).data, message="Detection retrieved."
        )


# ── Allow / Block Lists ────────────────────────────────────────────────────


class AllowListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenants = Tenant.objects.filter(user=request.user, is_active=True)
        entries = AllowList.objects.filter(tenant__in=tenants)
        return success(data=AllowListSerializer(entries, many=True).data, message="Allow list retrieved.")

    def post(self, request):
        serializer = DomainInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = Tenant.objects.filter(user=request.user, is_active=True).first()
        if not tenant:
            return error(message="No active tenant found.", status_code=status.HTTP_400_BAD_REQUEST)

        entry, created = AllowList.objects.get_or_create(
            tenant=tenant,
            domain=serializer.validated_data["domain"].lower(),
            defaults={
                "added_by": request.user,
                "reason": serializer.validated_data.get("reason", ""),
            },
        )
        if not created:
            return error(message="Domain already in allow list.", status_code=status.HTTP_409_CONFLICT)

        return success(
            data=AllowListSerializer(entry).data,
            message="Domain added to allow list.",
            status_code=status.HTTP_201_CREATED,
        )


class BlockListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenants = Tenant.objects.filter(user=request.user, is_active=True)
        entries = BlockList.objects.filter(tenant__in=tenants)
        return success(data=BlockListSerializer(entries, many=True).data, message="Block list retrieved.")

    def post(self, request):
        serializer = DomainInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = Tenant.objects.filter(user=request.user, is_active=True).first()
        if not tenant:
            return error(message="No active tenant found.", status_code=status.HTTP_400_BAD_REQUEST)

        entry, created = BlockList.objects.get_or_create(
            tenant=tenant,
            domain=serializer.validated_data["domain"].lower(),
            defaults={
                "added_by": request.user,
                "reason": serializer.validated_data.get("reason", ""),
            },
        )
        if not created:
            return error(message="Domain already in block list.", status_code=status.HTTP_409_CONFLICT)

        return success(
            data=BlockListSerializer(entry).data,
            message="Domain added to block list.",
            status_code=status.HTTP_201_CREATED,
        )


# ── Feedback ────────────────────────────────────────────────────────────────


class FeedbackReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FeedbackCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save()
        return success(
            data={"id": str(feedback.id)},
            message="Feedback submitted.",
            status_code=status.HTTP_201_CREATED,
        )


# ── Dashboard ───────────────────────────────────────────────────────────────


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenants = Tenant.objects.filter(user=request.user, is_active=True)

        total_emails = Message.objects.filter(mailbox__tenant__in=tenants).count()

        stats = Detection.objects.filter(
            message__mailbox__tenant__in=tenants
        ).aggregate(
            total=Count("id"),
            safe=Count("id", filter=Q(verdict="safe")),
            suspicious=Count("id", filter=Q(verdict="suspicious")),
            phishing=Count("id", filter=Q(verdict="phishing")),
        )

        total_mailboxes = Mailbox.objects.filter(tenant__in=tenants).count()

        recent = (
            Detection.objects.filter(message__mailbox__tenant__in=tenants)
            .select_related("message__mailbox")
            .order_by("-created_at")[:10]
        )

        # Daily stats (30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_stats = []
        for i in range(30):
            day = thirty_days_ago + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_qs = Detection.objects.filter(
                message__mailbox__tenant__in=tenants,
                created_at__gte=day_start,
                created_at__lt=day_end,
            )
            daily_stats.append(
                {
                    "date": day_start.strftime("%Y-%m-%d"),
                    "total": day_qs.count(),
                    "threats": day_qs.filter(verdict__in=["suspicious", "phishing"]).count(),
                }
            )

        return success(
            data={
                "total_emails_scanned": total_emails,
                "total_threats": (stats["suspicious"] or 0) + (stats["phishing"] or 0),
                "total_safe": stats["safe"] or 0,
                "total_suspicious": stats["suspicious"] or 0,
                "total_phishing": stats["phishing"] or 0,
                "total_mailboxes": total_mailboxes,
                "total_tenants": tenants.count(),
                "recent_detections": DetectionListSerializer(recent, many=True).data,
                "daily_stats": daily_stats,
            },
            message="Dashboard data retrieved.",
        )
