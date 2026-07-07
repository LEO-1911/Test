"""Kosten-Guard für die Claude-API (USP 7): Tagesbudget mit Hard-Stop.

Jeder Call wird VOR der Ausführung gegen das Budget geprüft (konservative
Schätzung) und NACH der Ausführung mit echten Token-Zahlen verbucht. Bei
Überschreitung pausieren KI-Features — Quant-Features laufen immer weiter."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import AiUsageRow
from backend.settings import load_config


class BudgetExceeded(RuntimeError):
    pass


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = load_config("ai")["pricing_usd_per_mtok"]
    if model not in pricing:
        raise ValueError(f"Kein Preis für Modell {model!r} in config/ai.yaml")
    p = pricing[model]
    return (input_tokens * float(p["input"]) + output_tokens * float(p["output"])) / 1_000_000


def spent_today(session: Session) -> float:
    midnight = datetime.combine(datetime.utcnow().date(), time.min)
    total = session.scalar(
        select(func.sum(AiUsageRow.cost_usd)).where(AiUsageRow.ts_utc >= midnight)
    )
    return float(total or 0.0)


def budget_status(session: Session) -> dict[str, Any]:
    cfg = load_config("ai")["budget"]
    daily = float(cfg["daily_usd"])
    spent = spent_today(session)
    return {
        "daily_usd": daily,
        "spent_usd": round(spent, 4),
        "remaining_usd": round(max(0.0, daily - spent), 4),
        "exhausted": spent >= daily,
        "warn": spent >= daily * float(cfg.get("warn_at_pct", 80)) / 100,
    }


def ensure_budget(session: Session, estimated_cost: float) -> None:
    """Hard-Stop VOR dem API-Call: geschätzte Kosten müssen ins Restbudget passen."""
    status = budget_status(session)
    if status["spent_usd"] + estimated_cost > status["daily_usd"]:
        raise BudgetExceeded(
            f"Tagesbudget erschöpft: {status['spent_usd']:.2f} $ von "
            f"{status['daily_usd']:.2f} $ verbraucht (Hard-Stop, config/ai.yaml)"
        )


def record_usage(
    session: Session, model: str, purpose: str, input_tokens: int, output_tokens: int
) -> float:
    cost = cost_for(model, input_tokens, output_tokens)
    session.add(AiUsageRow(
        model=model, purpose=purpose,
        input_tokens=input_tokens, output_tokens=output_tokens,
        cost_usd=cost,
    ))
    return cost
