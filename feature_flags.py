from typing import Dict

from storage.sqlite_store import SQLiteStore
from variaveis import flags


class FeatureFlagManager:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.defaults = {
            "CONTEXT_CORRECTION_ENABLED": flags.CONTEXT_CORRECTION_ENABLED,
            "SMART_ROUTING_ENABLED": flags.SMART_ROUTING_ENABLED,
            "GROQ_ENABLED": flags.GROQ_ENABLED,
            "GEMINI_ENABLED": flags.GEMINI_ENABLED,
            "INTEGRATIONS_GMAIL_ENABLED": flags.INTEGRATIONS_GMAIL_ENABLED,
            "INTEGRATIONS_CALENDAR_ENABLED": flags.INTEGRATIONS_CALENDAR_ENABLED,
            "INTEGRATIONS_TELEGRAM_ENABLED": flags.INTEGRATIONS_TELEGRAM_ENABLED,
            "INTEGRATIONS_DRIVE_ENABLED": flags.INTEGRATIONS_DRIVE_ENABLED,
            "INTEGRATIONS_LINKEDIN_ENABLED": flags.INTEGRATIONS_LINKEDIN_ENABLED,
            "INTEGRATIONS_WHATSAPP_ENABLED": flags.INTEGRATIONS_WHATSAPP_ENABLED,
            "INTEGRATIONS_WEB_AUTOMATION_ENABLED": flags.INTEGRATIONS_WEB_AUTOMATION_ENABLED,
            "AUTO_REPLY_ENABLED": flags.AUTO_REPLY_ENABLED,
            "PLAYWRIGHT_AUTOMATION_ENABLED": flags.PLAYWRIGHT_AUTOMATION_ENABLED,
            "FILE_CREATION_ENABLED": flags.FILE_CREATION_ENABLED,
        }
        self.bootstrap_defaults()

    def bootstrap_defaults(self) -> None:
        current = self.store.get_all_feature_flags()
        for flag_name, enabled in self.defaults.items():
            if flag_name not in current:
                self.store.set_feature_flag(flag_name, enabled)

    def is_enabled(self, flag_name: str) -> bool:
        value = self.store.get_feature_flag(flag_name)
        if value is None:
            return bool(self.defaults.get(flag_name, False))
        return bool(value)

    def set_flag(self, flag_name: str, enabled: bool) -> None:
        self.store.set_feature_flag(flag_name, bool(enabled))

    def as_dict(self) -> Dict[str, bool]:
        values = dict(self.defaults)
        values.update(self.store.get_all_feature_flags())
        return values
