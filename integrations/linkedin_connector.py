import os
import re
from typing import Any, Dict


class LinkedInConnector:
    

    def __init__(self, enabled: bool = True, automation_enabled: bool = True):
        self.enabled = enabled
        self.automation_enabled = automation_enabled
        self.email = os.getenv("LINKEDIN_EMAIL", "").strip()
        self.password = os.getenv("LINKEDIN_PASSWORD", "").strip()

    def _with_browser(self, callback):
        if not self.enabled:
            raise RuntimeError("LinkedIn connector disabled by feature flag")
        if not self.automation_enabled:
            raise RuntimeError("Playwright automation disabled")
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError(f"Playwright unavailable: {exc}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                result = callback(page)
            finally:
                context.close()
                browser.close()
            return result

    def _login(self, page):
        if not self.email or not self.password:
            raise RuntimeError("LINKEDIN_EMAIL / LINKEDIN_PASSWORD not configured")
        page.goto("https://www.linkedin.com/login", timeout=45000)
        page.fill("#username", self.email)
        page.fill("#password", self.password)
        page.click("button[type='submit']")
        page.wait_for_timeout(2000)

    def fetch_notifications(self) -> Dict[str, Any]:
        def run(page):
            self._login(page)
            page.goto("https://www.linkedin.com/notifications/", timeout=45000)
            page.wait_for_timeout(2000)
            items = page.locator("div.notifications-notifications-list__container li").all_inner_texts()
            return {"count": len(items), "items": items[:10]}

        return self._with_browser(run)

    def send_message(self, profile_url: str, message: str) -> Dict[str, Any]:
        def run(page):
            self._login(page)
            page.goto(profile_url, timeout=45000)
            page.wait_for_timeout(1500)
            
            if page.locator("button:has-text('Message')").count() == 0:
                raise RuntimeError("Message button not found on profile")
            page.click("button:has-text('Message')")
            page.wait_for_timeout(1200)
            textbox = page.locator("div.msg-form__contenteditable")
            textbox.fill(message)
            page.click("button.msg-form__send-button")
            page.wait_for_timeout(1000)
            return {"status": "sent", "profile_url": profile_url}

        return self._with_browser(run)

    def execute_command(self, command_text: str) -> Dict[str, Any]:
        text = (command_text or "").strip()
        if text.lower() in {"linkedin notifications", "check linkedin"}:
            data = self.fetch_notifications()
            return {"success": True, "message": f"Fetched {data.get('count', 0)} LinkedIn notifications.", "data": data}

        pattern = re.compile(r"linkedin message (https?://\S+) (.+)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            profile_url = match.group(1).strip()
            message = match.group(2).strip()
            data = self.send_message(profile_url, message)
            return {"success": True, "message": "LinkedIn message sent.", "data": data}

        return {"success": False, "message": "Unsupported LinkedIn command format.", "data": None}
