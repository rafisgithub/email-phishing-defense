import uuid
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.user.authentication import CookieJWTAuthentication
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
from .services.microsoft_graph import MicrosoftGraphService
from .tasks import sync_mailboxes


# ── Tenant / Connection Status ──────────────────────────────────────────────


class TenantListView(APIView):
    """List all tenants for the current user with connection health."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        tenants = Tenant.objects.filter(user=request.user)
        data = []
        for tenant in tenants:
            info = TenantSerializer(tenant).data
            graph = MicrosoftGraphService(tenant)
            health = graph.check_health()

            # Auto-fill org name if missing
            if health["org_name"] and not tenant.name:
                tenant.name = health["org_name"]
                tenant.save(update_fields=["name"])
                info["name"] = health["org_name"]

            info["is_connected"] = health["permissions_ok"]
            info["token_ok"] = health["token_ok"]
            info["api_ok"] = health["api_ok"]
            info["permissions_ok"] = health["permissions_ok"]
            info["error"] = health["error"]
            info["missing_permissions"] = health["missing_permissions"]
            info["token_expires_at"] = (
                tenant.token_expires_at.isoformat() if tenant.token_expires_at else None
            )
            data.append(info)
        return success(data=data, message="Tenants retrieved.")


class TenantStatusView(APIView):
    """Quick connection-health check (for polling)."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        tenants = Tenant.objects.filter(user=request.user, is_active=True)
        if not tenants.exists():
            return success(
                data={"connected": False, "tenant_count": 0, "tenants": [], "error": ""},
                message="No tenants connected.",
            )

        tenant_statuses = []
        any_connected = False
        global_error = ""
        for tenant in tenants:
            graph = MicrosoftGraphService(tenant)
            health = graph.check_health()

            if health["org_name"] and not tenant.name:
                tenant.name = health["org_name"]
                tenant.save(update_fields=["name"])

            if health["permissions_ok"]:
                any_connected = True

            if health["error"] and not global_error:
                global_error = health["error"]

            tenant_statuses.append({
                "id": str(tenant.id),
                "name": tenant.name or tenant.tenant_id,
                "connected": health["permissions_ok"],
                "token_ok": health["token_ok"],
                "error": health["error"],
                "missing_permissions": health["missing_permissions"],
                "last_synced_at": (
                    tenant.last_synced_at.isoformat() if tenant.last_synced_at else None
                ),
            })

        return success(
            data={
                "connected": any_connected,
                "tenant_count": tenants.count(),
                "tenants": tenant_statuses,
                "error": global_error,
            },
            message="Connection status retrieved.",
        )


class TenantResyncView(APIView):
    """Force token refresh and re-sync mailboxes."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, tenant_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id, user=request.user)
        except Tenant.DoesNotExist:
            return error(message="Tenant not found.", status_code=status.HTTP_404_NOT_FOUND)

        # Force refresh token
        tenant._access_token = ""
        tenant.token_expires_at = None
        tenant.save(update_fields=["_access_token", "token_expires_at"])

        graph = MicrosoftGraphService(tenant)
        health = graph.check_health()

        if not health["permissions_ok"]:
            return error(
                message=health["error"] or "Cannot connect to Microsoft Graph API.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Update org name
        if health["org_name"] and not tenant.name:
            tenant.name = health["org_name"]
            tenant.save(update_fields=["name"])

        # Trigger mailbox sync
        sync_mailboxes.delay(str(tenant.id))

        return success(
            data=TenantSerializer(tenant).data,
            message="Token refreshed. Mailbox sync started.",
        )


# ── M365 Connection ─────────────────────────────────────────────────────────


class ConnectM365View(APIView):
    """Generate the Microsoft 365 admin-consent URL."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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
    authentication_classes = [CookieJWTAuthentication]

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


# ── Test / Demo ─────────────────────────────────────────────────────────────


class TestAnalyzeEmailView(APIView):
    """
    POST an email payload and get the detection result back instantly.
    For Postman / development testing only.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        from .services.phishing_detector import PhishingDetector
        from .services.llm_explainer import generate_explanation, _fallback_explanation

        data = request.data
        required = ["sender_email", "subject", "body_text"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return error(
                message=f"Missing required fields: {', '.join(missing)}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Build email_data for the detector
        email_data = {
            "sender_email": data.get("sender_email", ""),
            "sender_name": data.get("sender_name", ""),
            "reply_to": data.get("reply_to", ""),
            "subject": data.get("subject", ""),
            "body_text": data.get("body_text", ""),
            "body_html": data.get("body_html", ""),
            "extracted_links": data.get("extracted_links", []),
            "attachments_meta": data.get("attachments_meta", []),
            "headers": data.get("headers", {}),
            "to_recipients": data.get("to_recipients", []),
            "cc_recipients": data.get("cc_recipients", []),
        }

        # Load allow/block lists for this user's tenants
        tenants = Tenant.objects.filter(user=request.user, is_active=True)
        allow = list(AllowList.objects.filter(tenant__in=tenants).values_list("domain", flat=True))
        block = list(BlockList.objects.filter(tenant__in=tenants).values_list("domain", flat=True))
        vips = list(
            Mailbox.objects.filter(tenant__in=tenants, is_vip=True).values_list("email", flat=True)
        )

        # Run detection
        detector = PhishingDetector(allow_list=allow, block_list=block, vip_emails=vips)
        result = detector.analyze(email_data)

        # Build a mock detection object for the LLM explainer
        class _MockDetection:
            pass

        mock_det = _MockDetection()
        mock_det.verdict = result["verdict"]
        mock_det.score = result["score"]
        mock_det.reason_codes = result["reason_codes"]
        mock_det.evidence = result["evidence"]

        # Build a mock message
        class _MockMessage:
            pass

        mock_msg = _MockMessage()
        mock_msg.subject = email_data["subject"]
        mock_msg.body_text = email_data["body_text"]
        mock_msg.sender_email = email_data["sender_email"]
        mock_msg.reply_to = email_data["reply_to"]
        mock_det.message = mock_msg

        # Generate LLM explanation (falls back to static if no API key)
        try:
            llm_explanation = generate_explanation(mock_det)
        except Exception:
            llm_explanation = _fallback_explanation(mock_det)

        return success(
            data={
                "score": result["score"],
                "verdict": result["verdict"],
                "reason_codes": result["reason_codes"],
                "explanations": result["explanations"],
                "evidence": result["evidence"],
                "rules_applied": result["rules_applied"],
                "llm_explanation": llm_explanation,
            },
            message=f"Email analyzed: {result['verdict']}.",
        )
