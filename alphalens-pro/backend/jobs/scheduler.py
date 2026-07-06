"""APScheduler-Anbindung: tägliches Daten-Update laut config/schedule.yaml.

Start:  python -m backend.jobs.scheduler
(In MS11 kommt der Scheduler in den FastAPI-Lifespan; bis dahin läuft er als
eigener Prozess oder man stößt Updates manuell mit `make update` an.)"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.data.pipeline import run_daily_update
from backend.settings import load_config

log = logging.getLogger(__name__)


def build_scheduler() -> BlockingScheduler:
    cfg = load_config("schedule")["daily_update"]
    hour, minute = str(cfg.get("time", "07:30")).split(":")
    day_of_week = "mon-fri" if cfg.get("weekdays_only", True) else "*"
    scheduler = BlockingScheduler(timezone=str(cfg.get("timezone", "Europe/Berlin")))
    scheduler.add_job(
        lambda: log.info("Daily update: %s", run_daily_update()),
        CronTrigger(day_of_week=day_of_week, hour=int(hour), minute=int(minute)),
        id="daily_update",
        misfire_grace_time=3600,
    )
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log.info("Scheduler gestartet — Zeiten aus config/schedule.yaml")
    build_scheduler().start()


if __name__ == "__main__":
    main()
