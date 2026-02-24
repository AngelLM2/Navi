from typing import Any, Dict, Optional

from audit_logger import AuditLogger
from feature_flags import FeatureFlagManager
from integrations.autoresponse import AutoResponder
from integrations.calendar_connector import CalendarConnector
from integrations.drive_connector import DriveConnector
from integrations.gmail_connector import GmailConnector
from integrations.linkedin_connector import LinkedInConnector
from integrations.telegram_connector import TelegramConnector
from integrations.web_automation_connector import WebAutomationConnector
from integrations.whatsapp_connector import WhatsAppConnector
from storage.sqlite_store import SQLiteStore


class IntegrationHub:
    def __init__(
        self,
        store: SQLiteStore,
        flags: FeatureFlagManager,
        audit: Optional[AuditLogger] = None,
        planner=None,
    ):
        self.store = store
        self.flags = flags
        self.audit = audit
        self.autoresponder = AutoResponder()

        self.gmail = GmailConnector(store, enabled=flags.is_enabled("INTEGRATIONS_GMAIL_ENABLED"))
        self.calendar = CalendarConnector(store, enabled=flags.is_enabled("INTEGRATIONS_CALENDAR_ENABLED"))
        self.drive = DriveConnector(store, enabled=flags.is_enabled("INTEGRATIONS_DRIVE_ENABLED"))
        self.telegram = TelegramConnector(enabled=flags.is_enabled("INTEGRATIONS_TELEGRAM_ENABLED"))
        self.linkedin = LinkedInConnector(
            enabled=flags.is_enabled("INTEGRATIONS_LINKEDIN_ENABLED"),
            automation_enabled=flags.is_enabled("PLAYWRIGHT_AUTOMATION_ENABLED"),
        )
        self.whatsapp = WhatsAppConnector(
            enabled=flags.is_enabled("INTEGRATIONS_WHATSAPP_ENABLED"),
            automation_enabled=flags.is_enabled("PLAYWRIGHT_AUTOMATION_ENABLED"),
        )
        self.web = WebAutomationConnector(
            store=self.store,
            enabled=flags.is_enabled("INTEGRATIONS_WEB_AUTOMATION_ENABLED"),
            automation_enabled=flags.is_enabled("PLAYWRIGHT_AUTOMATION_ENABLED"),
            planner=planner,
        )
        try:
            self.web.bootstrap_default_profiles(force=False)
        except Exception:
            pass

    def set_planner(self, planner) -> None:
        self.web.set_planner(planner)

    def evaluate_autoreply(
        self,
        channel: str,
        text: str,
        sender: str = "",
        subject: str = "",
        target: str = "",
    ) -> Dict[str, Any]:
        decision = self.autoresponder.decide(channel=channel, text=text, sender=sender, subject=subject)
        if self.audit:
            self.audit.log_integration_event(
                platform=channel,
                event_type="autoresponse_decision",
                confidence=float(decision.get("confidence", 0.0)),
                decision=str(decision.get("decision", "")),
                details=decision,
            )

        if not self.flags.is_enabled("AUTO_REPLY_ENABLED"):
            decision["decision"] = "block"
            decision["reason"] = "global_kill_switch"
            return decision

        if decision.get("decision") == "auto_send":
            try:
                send_result = self._send_auto_response(channel, target, decision.get("response", "Acknowledged."))
                decision["send_result"] = send_result
                decision["sent"] = True
            except Exception as exc:
                decision["sent"] = False
                decision["error"] = str(exc)
        return decision

    def _send_auto_response(self, channel: str, target: str, response_text: str) -> Dict[str, Any]:
        channel = (channel or "").lower()
        if channel == "telegram":
            return self.telegram.send_message(response_text, chat_id=target or None)
        if channel == "gmail":
            if not target:
                raise RuntimeError("Missing gmail recipient target")
            return self.gmail.send_message(target, "Re: quick reply", response_text)
        if channel == "whatsapp":
            if not target:
                raise RuntimeError("Missing whatsapp target contact")
            return self.whatsapp.send_message(target, response_text)
        if channel == "linkedin":
            if not target:
                raise RuntimeError("Missing linkedin profile url target")
            return self.linkedin.send_message(target, response_text)
        raise RuntimeError(f"Unsupported auto-response channel: {channel}")

    def dispatch_command(self, command_text: str) -> Optional[Dict[str, Any]]:
        text = (command_text or "").strip().lower()
        try:
            if text.startswith("gmail"):
                return self.gmail.execute_command(command_text)
            if text.startswith("calendar"):
                return self.calendar.execute_command(command_text)
            if text.startswith("drive"):
                return self.drive.execute_command(command_text)
            if text.startswith("telegram"):
                return self.telegram.execute_command(command_text)
            if text.startswith("linkedin"):
                return self.linkedin.execute_command(command_text)
            if text.startswith("whatsapp"):
                return self.whatsapp.execute_command(command_text)
            if text.startswith("web"):
                return self.web.execute_command(command_text)
        except Exception as exc:
            return {"success": False, "message": f"Integration error: {exc}", "data": None}
        return None

    def enqueue_task(self, platform: str, task_type: str, payload: Dict[str, Any]) -> int:
        return self.store.enqueue_integration_task(platform=platform, task_type=task_type, payload=payload)

    def _execute_task(self, platform: str, task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        platform = (platform or "").lower()
        if task_type == "autorespond":
            return self.evaluate_autoreply(
                channel=platform,
                text=payload.get("text", ""),
                sender=payload.get("sender", ""),
                subject=payload.get("subject", ""),
                target=payload.get("target", ""),
            )
        if platform == "gmail":
            if task_type == "send":
                return self.gmail.send_message(payload["to"], payload.get("subject", ""), payload.get("body", ""))
            if task_type == "draft":
                return self.gmail.create_draft(payload["to"], payload.get("subject", ""), payload.get("body", ""))
            if task_type == "summarize":
                return {"summary": self.gmail.summarize_inbox(max_results=int(payload.get("max_results", 10)))}
        elif platform == "calendar":
            if task_type == "create_event":
                return self.calendar.create_event(
                    title=payload["title"],
                    start_iso=payload["start_iso"],
                    end_iso=payload["end_iso"],
                    description=payload.get("description", ""),
                )
            if task_type == "list":
                return {"events": self.calendar.list_upcoming(max_results=int(payload.get("max_results", 10)))}
        elif platform == "drive":
            if task_type == "search":
                return {"files": self.drive.search_files(payload.get("query", ""))}
            if task_type == "list":
                return {"files": self.drive.list_files(page_size=int(payload.get("max_results", 10)))}
        elif platform == "telegram":
            if task_type == "send":
                return self.telegram.send_message(payload.get("text", ""), chat_id=payload.get("chat_id"))
        elif platform == "linkedin":
            if task_type == "message":
                return self.linkedin.send_message(payload["profile_url"], payload["message"])
            if task_type == "notifications":
                return self.linkedin.fetch_notifications()
        elif platform == "whatsapp":
            if task_type == "send":
                return self.whatsapp.send_message(payload["contact"], payload["message"])
            if task_type == "unread":
                return self.whatsapp.fetch_unread()
        elif platform == "web":
            if task_type == "run":
                return self.web.run_task(payload["profile_name"], payload.get("instruction", "collect summary"))
            if task_type == "refresh_profile":
                return self.web.refresh_profile(payload["profile_name"], force=True)
            if task_type == "refresh_due":
                return self.web.refresh_due_profiles(max_profiles=int(payload.get("max_profiles", 2)))
            if task_type == "report":
                return self.web.export_report(payload["profile_name"])
        raise RuntimeError(f"Unsupported task: {platform}/{task_type}")

    def run_periodic_refreshes(self) -> Dict[str, Any]:
        return self.web.refresh_due_profiles(max_profiles=2)

    def process_pending_tasks(self, limit: int = 10) -> int:
        tasks = self.store.get_pending_integration_tasks(limit=limit)
        processed = 0
        for task in tasks:
            task_id = int(task["id"])
            platform = str(task["platform"])
            task_type = str(task["task_type"])
            payload = task.get("payload", {})
            retries = int(task.get("retries", 0))
            try:
                result = self._execute_task(platform, task_type, payload)
                self.store.update_integration_task_status(task_id, "done", retries=retries)
                if self.audit:
                    self.audit.log_integration_event(
                        platform=platform,
                        event_type="task_done",
                        confidence=1.0,
                        decision="executed",
                        details={"task_type": task_type, "result": result},
                        task_id=task_id,
                    )
                processed += 1
            except Exception as exc:
                next_retries = retries + 1
                status = "failed" if next_retries >= 3 else "pending"
                self.store.update_integration_task_status(task_id, status, retries=next_retries)
                if self.audit:
                    self.audit.log_integration_event(
                        platform=platform,
                        event_type="task_error",
                        confidence=0.0,
                        decision="retry" if status == "pending" else "failed",
                        details={"task_type": task_type, "error": str(exc), "retries": next_retries},
                        task_id=task_id,
                    )
        return processed
