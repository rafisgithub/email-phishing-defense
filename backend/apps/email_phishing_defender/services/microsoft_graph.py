import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
AUTH_BASE_URL = "https://login.microsoftonline.com"


class MicrosoftGraphService:
    """Service for Microsoft Graph API interactions using application permissions."""

    def __init__(self, tenant):
        self.tenant = tenant
        self.client_id = settings.MS_CLIENT_ID
        self.client_secret = settings.MS_CLIENT_SECRET

    # ── Auth ────────────────────────────────────────────────────────────

    @staticmethod
    def get_admin_consent_url(redirect_uri, state=""):
        """Build the admin consent URL for a Microsoft 365 tenant."""
        client_id = settings.MS_CLIENT_ID
        return (
            f"{AUTH_BASE_URL}/common/adminconsent"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )

    def get_access_token(self):
        """Obtain a valid access token, refreshing from cache when possible."""
        if (
            self.tenant._access_token
            and self.tenant.token_expires_at
            and self.tenant.token_expires_at > timezone.now()
        ):
            return self.tenant.access_token  # uses decrypt property

        url = f"{AUTH_BASE_URL}/{self.tenant.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        token_data = response.json()

        self.tenant.access_token = token_data["access_token"]
        self.tenant.token_expires_at = timezone.now() + timedelta(
            seconds=token_data.get("expires_in", 3600) - 300
        )
        self.tenant.save(update_fields=["_access_token", "token_expires_at"])

        return token_data["access_token"]

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json",
        }

    # ── Users / Mailboxes ───────────────────────────────────────────────

    def fetch_users(self):
        """Fetch all users (mailboxes) from the tenant."""
        url = (
            f"{GRAPH_BASE_URL}/users"
            "?$select=id,displayName,mail,userPrincipalName"
            "&$top=999"
        )
        users = []
        while url:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            users.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return users

    # ── Messages ────────────────────────────────────────────────────────

    def fetch_messages(self, user_id, since=None, top=50):
        """Fetch emails for a user mailbox."""
        url = (
            f"{GRAPH_BASE_URL}/users/{user_id}/messages"
            f"?$top={top}"
            "&$orderby=receivedDateTime desc"
            "&$select=id,sender,replyTo,subject,body,bodyPreview,"
            "receivedDateTime,hasAttachments,internetMessageHeaders,"
            "toRecipients,ccRecipients"
        )
        if since:
            iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            url += f"&$filter=receivedDateTime ge {iso}"

        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def fetch_message_attachments(self, user_id, message_id):
        """Fetch attachment metadata for a specific message."""
        url = (
            f"{GRAPH_BASE_URL}/users/{user_id}/messages/{message_id}"
            "/attachments?$select=id,name,contentType,size"
        )
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])

    # ── Actions ─────────────────────────────────────────────────────────

    def move_message(self, user_id, message_id, destination_folder="junkemail"):
        """Move a message to the given folder (default: Junk Email)."""
        url = f"{GRAPH_BASE_URL}/users/{user_id}/messages/{message_id}/move"
        resp = requests.post(
            url,
            headers=self._headers(),
            json={"destinationId": destination_folder},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def apply_category(self, user_id, message_id, categories):
        """Apply category labels to a message."""
        url = f"{GRAPH_BASE_URL}/users/{user_id}/messages/{message_id}"
        resp = requests.patch(
            url,
            headers=self._headers(),
            json={"categories": categories},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
