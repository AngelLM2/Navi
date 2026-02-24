import re
from typing import Any, Dict


class WhatsAppConnector:
    

    def __init__(self, enabled: bool = True, automation_enabled: bool = True):
        self.enabled = enabled
        self.automation_enabled = automation_enabled

    def _with_browser(self, callback):
        if not self.enabled:
            raise RuntimeError("WhatsApp connector disabled by feature flag")
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

    def fetch_unread(self) -> Dict[str, Any]:
        def run(page):
            page.goto("https://web.whatsapp.com", timeout=60000)
            page.wait_for_timeout(4000)
            unread_badges = page.locator("span[aria-label*='unread message']").count()
            return {"unread_count": unread_badges}

        return self._with_browser(run)

    def send_message(self, contact: str, message: str) -> Dict[str, Any]:
        def run(page):
            page.goto("https://web.whatsapp.com", timeout=60000)
            page.wait_for_timeout(4000)
            search = page.locator("div[contenteditable='true'][data-tab='3']").first
            search.fill(contact)
            page.wait_for_timeout(1500)
            page.keyboard.press("Enter")
            box = page.locator("div[contenteditable='true'][data-tab='10']").first
            box.fill(message)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)
            return {"status": "sent", "contact": contact}

        return self._with_browser(run)

    def execute_command(self, command_text: str) -> Dict[str, Any]:
        text = (command_text or "").strip()
        if text.lower() in {"whatsapp unread", "check whatsapp"}:
            data = self.fetch_unread()
            return {"success": True, "message": f"WhatsApp unread count: {data.get('unread_count', 0)}", "data": data}

        pattern = re.compile(r"whatsapp send to (.+?) message (.+)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            contact = match.group(1).strip()
            message = match.group(2).strip()
            data = self.send_message(contact, message)
            return {"success": True, "message": f"WhatsApp message sent to {contact}.", "data": data}

        return {"success": False, "message": "Unsupported WhatsApp command format.", "data": None}
