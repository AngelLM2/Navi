from typing import Optional

from integrations.hub import IntegrationHub


class TaskScheduler:
    def __init__(self, hub: IntegrationHub):
        self.hub = hub
        self._scheduler = None

    def start(self) -> bool:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except Exception:
            self._scheduler = None
            return False

        if self._scheduler:
            return True
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(self._run_pending_tasks, "interval", seconds=30, id="integration_tasks")
        self._scheduler.add_job(self._export_snapshot, "interval", minutes=10, id="sqlite_snapshot")
        self._scheduler.add_job(self._run_periodic_refreshes, "interval", minutes=20, id="periodic_integrations")
        self._scheduler.start()
        return True

    def _run_pending_tasks(self):
        self.hub.process_pending_tasks(limit=20)

    def _export_snapshot(self):
        self.hub.store.export_snapshot()

    def _run_periodic_refreshes(self):
        try:
            self.hub.run_periodic_refreshes()
        except Exception:
            pass

    def stop(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
