import re
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def normalize_email(raw_message, attachments_meta=None):
    """
    Normalize a raw Microsoft Graph message dict into a unified schema.

    Returns a dict ready to be persisted as a ``Message`` model instance.
    """
    sender = raw_message.get("sender", {}).get("emailAddress", {})

    reply_to_list = raw_message.get("replyTo", [])
    reply_to = (
        reply_to_list[0].get("emailAddress", {}).get("address", "")
        if reply_to_list
        else ""
    )

    body = raw_message.get("body", {})
    body_content = body.get("content", "")
    body_type = body.get("contentType", "text")

    if body_type == "html":
        body_html = body_content
        body_text = _extract_text_from_html(body_content)
    else:
        body_text = body_content
        body_html = ""

    extracted_links = _extract_links_from_html(body_html) if body_html else []

    to_recipients = [
        r.get("emailAddress", {}).get("address", "")
        for r in raw_message.get("toRecipients", [])
    ]
    cc_recipients = [
        r.get("emailAddress", {}).get("address", "")
        for r in raw_message.get("ccRecipients", [])
    ]

    headers = {}
    for h in raw_message.get("internetMessageHeaders", []):
        headers[h.get("name", "")] = h.get("value", "")

    return {
        "ms_message_id": raw_message.get("id", ""),
        "sender_email": sender.get("address", ""),
        "sender_name": sender.get("name", ""),
        "reply_to": reply_to,
        "subject": raw_message.get("subject", ""),
        "body_text": body_text,
        "body_html": body_html,
        "received_at": raw_message.get("receivedDateTime", ""),
        "headers": headers,
        "extracted_links": extracted_links,
        "attachments_meta": attachments_meta or [],
        "to_recipients": to_recipients,
        "cc_recipients": cc_recipients,
        "has_attachments": raw_message.get("hasAttachments", False),
    }


# ── Helpers ─────────────────────────────────────────────────────────────────

def _extract_text_from_html(html_content):
    """Strip HTML tags and return plain text."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def _extract_links_from_html(html_content):
    """Return a list of ``{url, display_text}`` dicts extracted from <a> tags."""
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        links.append(
            {
                "url": a["href"],
                "display_text": a.get_text(strip=True),
            }
        )
    return links
