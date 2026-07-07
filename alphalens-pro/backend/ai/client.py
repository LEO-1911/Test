"""Claude-Client für Deep-Dives (Sonnet). Verhaltensregeln:

- Kein API-Key oder Budget erschöpft -> sauberer Skip mit Begründung, nie Crash.
- Budget-Prüfung VOR dem Call (Schätzung), Verbuchung NACH dem Call (echte Tokens).
- Die Analyse ist Kommentar zur Quant-Auswahl — die Auswahl selbst trifft
  ausschließlich die Scoring-Engine (kein KI-Stock-Picking durch die Hintertür)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.ai.budget import BudgetExceeded, ensure_budget, record_usage
from backend.settings import load_config, secrets

log = logging.getLogger(__name__)

DEEP_DIVE_SYSTEM = (
    "Du bist ein nüchterner Quant-Analyst. Du bekommst den Score-Breakdown eines "
    "Aktien-Picks (rein quantitativ ausgewählt). Schreibe auf Deutsch, kompakt, "
    "ohne Marketing-Ton: THESE (1 Satz), BULL CASE (2-3 Punkte), BEAR CASE (2-3 "
    "Punkte), KATALYSATOREN (falls aus den Daten ableitbar), KONFIDENZ (niedrig/"
    "mittel/hoch mit Begründung). Erfinde keine Zahlen: nutze nur die gelieferten "
    "Datenpunkte und sage offen, wenn Daten fehlen."
)


def deep_dive_pick(session: Session, ticker: str, context: dict[str, Any]) -> dict[str, Any]:
    """Sonnet-Analyse eines Wochen-Picks. Liefert {'analysis': ...} oder
    {'skipped': Grund} — der Picker funktioniert in beiden Fällen."""
    api_key = secrets().anthropic_api_key
    if not api_key:
        return {"skipped": "kein ANTHROPIC_API_KEY in .env — Quant-Pick ohne KI-Kommentar"}
    cfg = load_config("ai")
    model = str(cfg["models"]["deep"])
    try:
        ensure_budget(session, float(cfg["deep_dive"]["est_cost_usd"]))
    except BudgetExceeded as exc:
        return {"skipped": str(exc)}
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        import json

        message = client.messages.create(
            model=model,
            max_tokens=int(cfg["deep_dive"]["max_tokens"]),
            system=DEEP_DIVE_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"Pick: {ticker}\n"
                    f"Score-Breakdown und Kontext (JSON):\n"
                    f"{json.dumps(context, ensure_ascii=False, default=str)}"
                ),
            }],
        )
        cost = record_usage(
            session, model, "pick_deep_dive",
            message.usage.input_tokens, message.usage.output_tokens,
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        return {"analysis": text, "model": model, "cost_usd": round(cost, 4)}
    except Exception as exc:  # noqa: BLE001 — KI-Ausfall darf den Picker nie stoppen
        log.warning("Deep-Dive für %s fehlgeschlagen: %s", ticker, exc)
        return {"skipped": f"KI-Aufruf fehlgeschlagen: {exc}"}
