import hashlib
import re
from typing import Any, Dict, Optional, Set

from variaveis import runtime


class AutoResponder:
    def __init__(self):
        self.send_threshold = runtime.AUTO_REPLY_CONFIDENCE_SEND
        self.suggest_threshold = runtime.AUTO_REPLY_CONFIDENCE_SUGGEST
        self.sensitive_keywords = {
            "bank",
            "payment",
            "wire",
            "contract",
            "legal",
            "security",
            "password",
            "2fa",
            "invoice",
            "account change",
            "ssn",
            "tax",
        }
        self.faq_patterns = [
            (re.compile(r"\bthanks?\b|\bthank you\b", re.IGNORECASE), "You're welcome."),
            (re.compile(r"\bavailable\b.*\bmeeting\b", re.IGNORECASE), "I received your message. I will confirm shortly."),
            (re.compile(r"\bETA\b|\bwhen\b.*\bdeliver\b", re.IGNORECASE), "Acknowledged. I will provide an update soon."),
        ]

    def classify(self, text: str, sender: str = "", subject: str = "") -> Dict[str, Any]:
        message = f"{subject} {text}".lower()
        sensitive = any(keyword in message for keyword in self.sensitive_keywords)
        if sensitive:
            return {"category": "sensitive", "confidence": 0.95, "sensitive": True}

        for pattern, _ in self.faq_patterns:
            if pattern.search(message):
                return {"category": "faq", "confidence": 0.88, "sensitive": False}

        urgent = any(word in message for word in {"urgent", "asap", "immediately", "critical"})
        if urgent:
            return {"category": "urgent", "confidence": 0.83, "sensitive": False}

        if "newsletter" in message or "unsubscribe" in message:
            return {"category": "newsletter", "confidence": 0.82, "sensitive": False}

        return {"category": "general", "confidence": 0.65, "sensitive": False}

    def suggest_response(self, text: str, category: str) -> str:
        lower = (text or "").lower()
        for pattern, template in self.faq_patterns:
            if pattern.search(lower):
                return template
        if category == "urgent":
            return "I received this urgent message and will respond as soon as possible."
        if category == "newsletter":
            return "Acknowledged."
        return "Thanks for your message. I will reply soon."

    def decide(
        self,
        channel: str,
        text: str,
        sender: str = "",
        subject: str = "",
        allow_channels: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        allow_channels = allow_channels or {"gmail", "telegram", "whatsapp", "linkedin"}
        classification = self.classify(text, sender=sender, subject=subject)
        confidence = float(classification["confidence"])
        category = str(classification["category"])
        sensitive = bool(classification["sensitive"])
        response = self.suggest_response(text, category=category)
        payload_digest = hashlib.sha256(f"{channel}|{sender}|{subject}|{text}".encode("utf-8")).hexdigest()[:16]

        if channel not in allow_channels:
            return {
                "decision": "block",
                "reason": "channel_not_allowlisted",
                "confidence": confidence,
                "category": category,
                "response": response,
                "payload_digest": payload_digest,
            }

        if sensitive:
            return {
                "decision": "block",
                "reason": "sensitive_content",
                "confidence": confidence,
                "category": category,
                "response": response,
                "payload_digest": payload_digest,
            }

        if confidence >= self.send_threshold:
            return {
                "decision": "auto_send",
                "reason": "high_confidence_safe",
                "confidence": confidence,
                "category": category,
                "response": response,
                "payload_digest": payload_digest,
            }

        if confidence >= self.suggest_threshold:
            return {
                "decision": "suggest",
                "reason": "medium_confidence_review",
                "confidence": confidence,
                "category": category,
                "response": response,
                "payload_digest": payload_digest,
            }

        return {
            "decision": "block",
            "reason": "low_confidence",
            "confidence": confidence,
            "category": category,
            "response": response,
            "payload_digest": payload_digest,
        }
