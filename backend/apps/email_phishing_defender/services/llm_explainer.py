"""
LLM-powered explanation service for phishing detections.

Runs AFTER the detection engine has made its verdict.
The LLM does NOT override the verdict — it only explains it
in human-friendly language for the end user.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a cybersecurity assistant specializing in Microsoft 365 email threat analysis.

Your task is to clearly explain why an email was classified as phishing or safe.

You are part of a security system where:
- A detection engine (rules + ML) has already made the decision
- You MUST NOT change or question that decision
- You ONLY explain the reasoning based on provided signals and email data

STRICT RULES:
- Do NOT override the prediction
- Do NOT add reasons that are not in signals or clearly visible in the email
- Keep explanations simple and human-friendly (non-technical)
- Avoid generic explanations like "this looks suspicious" without specifics
- Prefer referencing actual words or patterns from the email

OUTPUT FORMAT (JSON ONLY):
{
  "summary": "Short explanation (1-2 lines)",
  "reasons": [
    "Specific reason 1",
    "Specific reason 2",
    "Specific reason 3"
  ],
  "risk_level": "low | medium | high",
  "user_advice": [
    "Clear action 1",
    "Clear action 2"
  ]
}"""

USER_PROMPT_TEMPLATE = """Email Subject:
"{subject}"

Email Body (first 1000 chars):
"{body}"

Sender:
"{sender_email}"

Reply-To:
"{reply_to}"

Prediction:
{verdict}

Confidence Score:
{score}/100

Detected Signals:
{signals}

Generate the JSON explanation."""


def _build_signals(reason_codes, evidence):
    """Convert reason_codes + evidence into readable signal strings."""
    from .phishing_detector import REASON_EXPLANATIONS

    signals = []
    for code in reason_codes:
        line = REASON_EXPLANATIONS.get(code, code.replace("_", " "))
        ev = evidence.get(code, {})
        if isinstance(ev, dict):
            details = ", ".join(f"{k}: {v}" for k, v in list(ev.items())[:3])
            if details:
                line += f" ({details})"
        signals.append(f"- {line}")
    return "\n".join(signals) if signals else "- No specific signals detected"


def generate_explanation(detection) -> dict:
    """
    Call the OpenAI API to generate a human-readable explanation.

    Returns a dict with keys: summary, reasons, risk_level, user_advice.
    Falls back to a static explanation on failure.
    """
    try:
        import openai
    except ImportError:
        logger.warning("openai package not installed, using fallback explanation")
        return _fallback_explanation(detection)

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        logger.warning("OPENAI_API_KEY not configured, using fallback explanation")
        return _fallback_explanation(detection)

    message = detection.message

    user_prompt = USER_PROMPT_TEMPLATE.format(
        subject=message.subject[:200],
        body=message.body_text[:1000],
        sender_email=message.sender_email,
        reply_to=message.reply_to or "(same as sender)",
        verdict=detection.verdict,
        score=detection.score,
        signals=_build_signals(detection.reason_codes, detection.evidence),
    )

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=getattr(settings, "LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        # Validate expected keys
        return {
            "summary": result.get("summary", ""),
            "reasons": result.get("reasons", []),
            "risk_level": result.get("risk_level", "medium"),
            "user_advice": result.get("user_advice", []),
        }

    except Exception as exc:
        logger.error("LLM explanation failed: %s", exc)
        return _fallback_explanation(detection)


def _fallback_explanation(detection) -> dict:
    """Static fallback when the LLM is unavailable."""
    from .phishing_detector import REASON_EXPLANATIONS

    reasons = [
        REASON_EXPLANATIONS.get(code, code.replace("_", " "))
        for code in (detection.reason_codes or [])
    ]

    if detection.verdict == "phishing":
        summary = "This email was flagged as a phishing attempt based on multiple suspicious indicators."
        risk_level = "high"
        advice = [
            "Do not click any links in this email.",
            "Do not download or open any attachments.",
            "Report this email to your IT security team.",
        ]
    elif detection.verdict == "suspicious":
        summary = "This email contains some suspicious elements that warrant caution."
        risk_level = "medium"
        advice = [
            "Verify the sender through an alternative channel before taking any action.",
            "Do not click links unless you can confirm they are legitimate.",
        ]
    else:
        summary = "This email appears to be safe with no significant phishing indicators."
        risk_level = "low"
        advice = [
            "No immediate action required.",
            "Always remain cautious with unexpected emails.",
        ]

    return {
        "summary": summary,
        "reasons": reasons[:5],
        "risk_level": risk_level,
        "user_advice": advice,
    }
