"""
Modular rule-based phishing detection engine.

Each rule returns ``{"score": int, "reason_code": str, "evidence": dict | None}``.
The engine aggregates results and clamps the total score to 0-100.
"""

import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Reference Data ──────────────────────────────────────────────────────────

SUSPICIOUS_DOMAINS = {
    "malicious-site.com", "phishing-example.com", "evil-domain.net",
    "fake-bank.com", "secure-update.info", "account-verify.net",
    "login-alert.com", "paypal-security.com", "microsoft-verify.net",
    "apple-id-confirm.com",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "bl.ink", "lnkd.in", "rb.gy", "cutt.ly",
}

FREEMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "mail.com", "protonmail.com", "zoho.com", "icloud.com", "yandex.com",
}

SUSPICIOUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".scr", ".pif", ".com", ".vbs", ".js",
    ".docm", ".xlsm", ".pptm", ".zip", ".rar", ".7z", ".iso", ".img",
}

URGENCY_KEYWORDS = [
    "urgent", "immediately", "action required", "verify your account",
    "suspend", "expire", "payment", "invoice", "reset password",
    "confirm your identity", "unusual activity", "security alert",
    "limited time", "act now", "final notice", "overdue",
]

CREDENTIAL_KEYWORDS = [
    "password", "credential", "login", "sign in", "ssn",
    "social security", "bank account", "credit card", "cvv",
    "pin number", "routing number", "tax return",
]

KNOWN_BRANDS = [
    "microsoft", "apple", "google", "amazon", "paypal", "netflix",
    "facebook", "instagram", "twitter", "linkedin", "dropbox",
    "wells fargo", "chase", "bank of america", "citibank",
]

VIP_TITLES = [
    "ceo", "cfo", "cto", "coo", "president", "director",
    "vice president", "vp", "chief", "founder", "owner",
]

CORPORATE_INDICATORS = [
    "inc", "ltd", "corp", "llc", "company", "group", "enterprise",
    "department", "team", "hr ", "human resources",
]

# ── Human-readable explanations ────────────────────────────────────────────

REASON_EXPLANATIONS = {
    "allowlisted": "This sender's domain is on your allow list and is considered trusted.",
    "reply_to_mismatch": "The reply-to address differs from the sender address, which is a common phishing tactic to redirect your responses to an attacker-controlled inbox.",
    "url_text_mismatch": "One or more links display a different URL than where they actually lead. Attackers use this to disguise malicious links as legitimate ones.",
    "suspicious_domain": "The sender's domain is flagged as a known suspicious or malicious domain.",
    "url_shortener": "The email contains shortened URLs (e.g. bit.ly, tinyurl). Attackers use URL shorteners to hide the true destination of malicious links.",
    "raw_ip_link": "The email contains links pointing to raw IP addresses instead of domain names, which is uncommon in legitimate emails and often used to bypass domain-based security filters.",
    "urgency_keywords": "The email uses urgent or threatening language (e.g. 'action required', 'account suspended') to pressure you into acting quickly without thinking.",
    "display_name_spoofing": "The sender's display name mimics a high-ranking executive (CEO, CFO, etc.) but the email comes from a free email provider, suggesting impersonation.",
    "external_sender_vip_target": "This email targets VIP users in your organization from an external free email account, a common pattern in spear-phishing attacks.",
    "suspicious_attachments": "The email contains potentially dangerous attachment types (.exe, .bat, .docm, etc.) that could contain malware or ransomware.",
    "freemail_corporate_claim": "The sender claims to represent a company or organization but is using a free email provider (Gmail, Yahoo, etc.), which is a strong indicator of impersonation.",
    "excessive_exclamation": "The email uses an unusual number of exclamation marks, which is a common trait of spam and phishing emails trying to create a sense of urgency.",
    "html_form_elements": "The email contains embedded HTML forms or password input fields, which are used to steal credentials directly within the email.",
    "fake_reply": "The email subject starts with 'Re:' or 'Fwd:' but has no prior conversation history, a trick used to make phishing emails appear like part of an ongoing thread.",
    "multiple_redirects": "Links in this email contain redirect parameters, which are used to bounce you through multiple URLs before reaching the final malicious destination.",
    "display_name_email_mismatch": "The sender's display name contains a different email address than the actual sender, a technique used to confuse recipients about the true origin.",
    "lookalike_domain": "The sender's domain closely resembles a well-known brand (e.g. 'micros0ft.com' instead of 'microsoft.com'). This is called typosquatting and is a common phishing technique.",
    "empty_body_with_links": "The email has very little text content but contains links, which is a common pattern in phishing emails that rely solely on tricking you into clicking.",
    "encoded_urls": "The email contains heavily encoded or obfuscated URLs, which are used to bypass security filters and hide the true destination.",
    "excessive_recipients": "The email was sent to an unusually large number of recipients, which is a hallmark of mass phishing or spam campaigns.",
    "credential_harvesting": "The email mentions sensitive information like passwords, credit cards, or SSNs, suggesting it may be attempting to harvest your credentials.",
    "brand_impersonation": "The email references a well-known brand (e.g. Microsoft, PayPal) but is sent from an unrelated domain, indicating a potential impersonation attack.",
    "blocklist_match": "The sender's domain is on your block list and has been flagged as untrusted.",
}


# ── Engine ──────────────────────────────────────────────────────────────────

class PhishingDetector:
    """Run a suite of phishing-detection rules against a normalised email."""

    def __init__(self, allow_list=None, block_list=None, vip_emails=None):
        self.allow_list = set(allow_list or [])
        self.block_list = set(block_list or [])
        self.vip_emails = set(vip_emails or [])

        self.rules = [
            self._reply_to_mismatch,
            self._url_text_mismatch,
            self._suspicious_domain,
            self._url_shortener,
            self._raw_ip_link,
            self._urgency_keywords,
            self._display_name_spoofing,
            self._external_sender_vip_target,
            self._suspicious_attachments,
            self._freemail_corporate_claim,
            self._excessive_exclamation,
            self._html_form_elements,
            self._fake_reply,
            self._multiple_redirects,
            self._display_name_email_mismatch,
            self._lookalike_domain,
            self._empty_body_with_links,
            self._encoded_urls,
            self._excessive_recipients,
            self._credential_harvesting,
            self._brand_impersonation,
            self._blocklist_match,
        ]

    # ── Public API ──────────────────────────────────────────────────────

    def analyze(self, email_data: dict) -> dict:
        sender_domain = self._domain(email_data.get("sender_email", ""))

        if sender_domain in self.allow_list:
            return {
                "score": 0,
                "verdict": "safe",
                "reason_codes": ["allowlisted"],
                "explanations": [REASON_EXPLANATIONS["allowlisted"]],
                "evidence": {"allowlisted_domain": sender_domain},
                "rules_applied": [],
            }

        total = 0
        reason_codes = []
        evidence = {}
        rules_applied = []

        for rule in self.rules:
            try:
                result = rule(email_data)
                if result and result["score"] > 0:
                    total += result["score"]
                    reason_codes.append(result["reason_code"])
                    if result.get("evidence"):
                        evidence[result["reason_code"]] = result["evidence"]
                    rules_applied.append(rule.__name__)
            except Exception as exc:
                logger.warning("Rule %s failed: %s", rule.__name__, exc)

        score = min(total, 100)
        if score >= 80:
            verdict = "phishing"
        elif score >= 50:
            verdict = "suspicious"
        else:
            verdict = "safe"

        explanations = [
            REASON_EXPLANATIONS[code]
            for code in reason_codes
            if code in REASON_EXPLANATIONS
        ]

        return {
            "score": score,
            "verdict": verdict,
            "reason_codes": reason_codes,
            "explanations": explanations,
            "evidence": evidence,
            "rules_applied": rules_applied,
        }

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _domain(email):
        if "@" in email:
            return email.split("@")[1].lower()
        return ""

    @staticmethod
    def _levenshtein(s1, s2):
        if len(s1) < len(s2):
            return PhishingDetector._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
            prev = curr
        return prev[-1]

    # ── Rules (22) ──────────────────────────────────────────────────────

    def _reply_to_mismatch(self, e):
        reply_to = e.get("reply_to", "")
        sender = e.get("sender_email", "")
        if reply_to and sender and reply_to.lower() != sender.lower():
            return {"score": 15, "reason_code": "reply_to_mismatch",
                    "evidence": {"sender": sender, "reply_to": reply_to}}
        return {"score": 0, "reason_code": "reply_to_mismatch"}

    def _url_text_mismatch(self, e):
        mismatches = []
        for link in e.get("extracted_links", []):
            display = link.get("display_text", "").strip()
            url = link.get("url", "")
            if display and re.match(r"https?://", display):
                d_host = urlparse(display).netloc.lower()
                u_host = urlparse(url).netloc.lower()
                if d_host and u_host and d_host != u_host:
                    mismatches.append({"display": display, "actual": url})
        if mismatches:
            return {"score": 20, "reason_code": "url_text_mismatch",
                    "evidence": {"mismatches": mismatches[:5]}}
        return {"score": 0, "reason_code": "url_text_mismatch"}

    def _suspicious_domain(self, e):
        domain = self._domain(e.get("sender_email", ""))
        if domain in SUSPICIOUS_DOMAINS:
            return {"score": 25, "reason_code": "suspicious_domain",
                    "evidence": {"domain": domain}}
        return {"score": 0, "reason_code": "suspicious_domain"}

    def _url_shortener(self, e):
        found = []
        for link in e.get("extracted_links", []):
            host = urlparse(link.get("url", "")).netloc.lower()
            if host in URL_SHORTENERS:
                found.append(link["url"])
        if found:
            return {"score": 10, "reason_code": "url_shortener",
                    "evidence": {"urls": found[:5]}}
        return {"score": 0, "reason_code": "url_shortener"}

    def _raw_ip_link(self, e):
        found = []
        for link in e.get("extracted_links", []):
            host = urlparse(link.get("url", "")).hostname or ""
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
                found.append(link["url"])
        if found:
            return {"score": 15, "reason_code": "raw_ip_link",
                    "evidence": {"urls": found[:5]}}
        return {"score": 0, "reason_code": "raw_ip_link"}

    def _urgency_keywords(self, e):
        text = f"{e.get('subject', '')} {e.get('body_text', '')}".lower()
        found = [kw for kw in URGENCY_KEYWORDS if kw in text]
        if found:
            return {"score": min(len(found) * 5, 20), "reason_code": "urgency_keywords",
                    "evidence": {"keywords": found}}
        return {"score": 0, "reason_code": "urgency_keywords"}

    def _display_name_spoofing(self, e):
        name = e.get("sender_name", "").lower()
        domain = self._domain(e.get("sender_email", ""))
        for title in VIP_TITLES:
            if title in name and domain in FREEMAIL_DOMAINS:
                return {"score": 20, "reason_code": "display_name_spoofing",
                        "evidence": {"name": e.get("sender_name"), "domain": domain}}
        return {"score": 0, "reason_code": "display_name_spoofing"}

    def _external_sender_vip_target(self, e):
        targets = [r for r in e.get("to_recipients", []) if r in self.vip_emails]
        domain = self._domain(e.get("sender_email", ""))
        if targets and domain in FREEMAIL_DOMAINS:
            return {"score": 10, "reason_code": "external_sender_vip_target",
                    "evidence": {"vip_targets": targets, "sender": e.get("sender_email")}}
        return {"score": 0, "reason_code": "external_sender_vip_target"}

    def _suspicious_attachments(self, e):
        bad = []
        for att in e.get("attachments_meta", []):
            name = att.get("name", "").lower()
            if any(name.endswith(ext) for ext in SUSPICIOUS_EXTENSIONS):
                bad.append(name)
        if bad:
            return {"score": 20, "reason_code": "suspicious_attachments",
                    "evidence": {"files": bad}}
        return {"score": 0, "reason_code": "suspicious_attachments"}

    def _freemail_corporate_claim(self, e):
        name = e.get("sender_name", "").lower()
        domain = self._domain(e.get("sender_email", ""))
        if domain in FREEMAIL_DOMAINS:
            if any(ind in name for ind in CORPORATE_INDICATORS):
                return {"score": 15, "reason_code": "freemail_corporate_claim",
                        "evidence": {"name": e.get("sender_name"), "domain": domain}}
        return {"score": 0, "reason_code": "freemail_corporate_claim"}

    def _excessive_exclamation(self, e):
        text = f"{e.get('subject', '')} {e.get('body_text', '')}"
        count = text.count("!")
        if count >= 5:
            return {"score": 5, "reason_code": "excessive_exclamation",
                    "evidence": {"count": count}}
        return {"score": 0, "reason_code": "excessive_exclamation"}

    def _html_form_elements(self, e):
        html = e.get("body_html", "").lower()
        indicators = ["<form", "<input", 'type="password"', "type='password'"]
        found = [i for i in indicators if i in html]
        if found:
            return {"score": 25, "reason_code": "html_form_elements",
                    "evidence": {"indicators": found}}
        return {"score": 0, "reason_code": "html_form_elements"}

    def _fake_reply(self, e):
        subject = e.get("subject", "")
        headers = e.get("headers", {})
        if re.match(r"^(Re|Fwd|FW):", subject, re.IGNORECASE):
            if not headers.get("In-Reply-To") and not headers.get("References"):
                return {"score": 10, "reason_code": "fake_reply",
                        "evidence": {"subject": subject}}
        return {"score": 0, "reason_code": "fake_reply"}

    def _multiple_redirects(self, e):
        indicators = ["redirect", "url=", "goto=", "redir=", "link=", "click."]
        found = []
        for link in e.get("extracted_links", []):
            url = link.get("url", "").lower()
            if any(i in url for i in indicators):
                found.append(link["url"])
        if found:
            return {"score": 10, "reason_code": "multiple_redirects",
                    "evidence": {"urls": found[:5]}}
        return {"score": 0, "reason_code": "multiple_redirects"}

    def _display_name_email_mismatch(self, e):
        name = e.get("sender_name", "")
        sender = e.get("sender_email", "")
        emails_in_name = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", name)
        for found in emails_in_name:
            if found.lower() != sender.lower():
                return {"score": 15, "reason_code": "display_name_email_mismatch",
                        "evidence": {"display_name": name, "sender": sender, "email_in_name": found}}
        return {"score": 0, "reason_code": "display_name_email_mismatch"}

    def _lookalike_domain(self, e):
        domain = self._domain(e.get("sender_email", ""))
        if not domain:
            return {"score": 0, "reason_code": "lookalike_domain"}
        name = domain.split(".")[0].lower()
        for brand in KNOWN_BRANDS:
            if name == brand:
                continue
            dist = self._levenshtein(name, brand)
            if 0 < dist <= 2:
                return {"score": 20, "reason_code": "lookalike_domain",
                        "evidence": {"domain": domain, "similar_to": brand}}
        return {"score": 0, "reason_code": "lookalike_domain"}

    def _empty_body_with_links(self, e):
        text = e.get("body_text", "").strip()
        links = e.get("extracted_links", [])
        if len(text) < 50 and len(links) > 0:
            return {"score": 10, "reason_code": "empty_body_with_links",
                    "evidence": {"body_length": len(text), "link_count": len(links)}}
        return {"score": 0, "reason_code": "empty_body_with_links"}

    def _encoded_urls(self, e):
        found = []
        for link in e.get("extracted_links", []):
            url = link.get("url", "")
            if re.search(r"[A-Za-z0-9+/]{40,}={0,2}", url):
                found.append(url)
            elif url.count("%") > 10:
                found.append(url)
        if found:
            return {"score": 10, "reason_code": "encoded_urls",
                    "evidence": {"urls": found[:5]}}
        return {"score": 0, "reason_code": "encoded_urls"}

    def _excessive_recipients(self, e):
        total = len(e.get("to_recipients", [])) + len(e.get("cc_recipients", []))
        if total > 20:
            return {"score": 10, "reason_code": "excessive_recipients",
                    "evidence": {"recipient_count": total}}
        return {"score": 0, "reason_code": "excessive_recipients"}

    def _credential_harvesting(self, e):
        text = f"{e.get('subject', '')} {e.get('body_text', '')}".lower()
        found = [kw for kw in CREDENTIAL_KEYWORDS if kw in text]
        if found:
            return {"score": min(len(found) * 5, 15), "reason_code": "credential_harvesting",
                    "evidence": {"keywords": found}}
        return {"score": 0, "reason_code": "credential_harvesting"}

    def _brand_impersonation(self, e):
        text = f"{e.get('subject', '')} {e.get('body_text', '')}".lower()
        sender_domain = self._domain(e.get("sender_email", ""))
        for brand in KNOWN_BRANDS:
            if brand in text and brand not in sender_domain:
                return {"score": 15, "reason_code": "brand_impersonation",
                        "evidence": {"brand": brand, "sender_domain": sender_domain}}
        return {"score": 0, "reason_code": "brand_impersonation"}

    def _blocklist_match(self, e):
        domain = self._domain(e.get("sender_email", ""))
        if domain in self.block_list:
            return {"score": 50, "reason_code": "blocklist_match",
                    "evidence": {"domain": domain}}
        return {"score": 0, "reason_code": "blocklist_match"}
