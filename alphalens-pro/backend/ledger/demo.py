"""Meilenstein-3-Demo: Hash-Chain, Append-only-Schutz, Manipulationserkennung,
Outcome-Auswertung und Brier-Score — in einer WEGWERF-Datenbank (data/ledger_demo.db),
damit das echte Ledger nicht mit Testeinträgen verunreinigt wird (es wäre ja
append-only, die Einträge blieben für immer).

    python -m backend.ledger.demo
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session, sessionmaker

from backend.data.providers.base import PriceBar
from backend.data.store import upsert_price_bars
from backend.db import Base
from backend.ledger.chain import append_entry, verify_chain
from backend.ledger.outcomes import evaluate_open_signals, stats_by_signal_type
from backend.settings import DATA_DIR


def _demo_session() -> Session:
    path = Path(DATA_DIR) / "ledger_demo.db"
    if path.exists():
        path.unlink()
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def main() -> None:  # noqa: PLR0915 — lineare Demo-Erzählung
    session = _demo_session()
    base_day = datetime(2026, 6, 1, 14, 30)

    print("1) Zwei Testsignale einbuchen (mit Zeitstempel, Preis, Wahrscheinlichkeit)…")
    s1 = append_entry(
        session, entry_type="signal", ticker="AAPL",
        payload={"signal_type": "breakout", "entry": 100.0, "stop": 95.0,
                 "target": 110.0, "horizon_days": 20, "why": "Demo"},
        price_at_creation=100.0, probability=0.65, ts_utc=base_day,
    )
    s2 = append_entry(
        session, entry_type="signal", ticker="AAPL",
        payload={"signal_type": "mean_reversion", "entry": 100.0, "stop": 96.0,
                 "target": 108.0, "horizon_days": 20, "why": "Demo"},
        price_at_creation=100.0, probability=0.55,
        ts_utc=base_day + timedelta(hours=1),
    )
    session.commit()
    print(f"   #{s1.id} hash={s1.entry_hash[:16]}…  prev={s1.prev_hash[:16]}…")
    print(f"   #{s2.id} hash={s2.entry_hash[:16]}…  prev={s2.prev_hash[:16]}… (verkettet)")

    print("\n2) Kette verifizieren:")
    print(f"   {verify_chain(session)}")

    print("\n3) Direktes UPDATE versuchen (Append-only-Trigger)…")
    try:
        session.execute(text("UPDATE ledger_entries SET price_at_creation = 1 WHERE id = 1"))
        session.commit()
        print("   FEHLER: UPDATE ging durch!")
    except DatabaseError as exc:
        session.rollback()
        print(f"   ✓ blockiert: {str(exc.orig).strip()}")

    print("\n4) Angreifer-Szenario: Trigger entfernen und Preis 'schönen'…")
    session.execute(text("DROP TRIGGER ledger_entries_no_update"))
    session.execute(text("UPDATE ledger_entries SET price_at_creation = 90.0 WHERE id = 1"))
    session.commit()
    result = verify_chain(session)
    print(f"   verify_chain: {result}")
    assert not result["valid"], "Manipulation hätte erkannt werden müssen!"
    print("   ✓ Manipulation erkannt — Kette bricht bei Eintrag "
          f"#{result['first_broken_id']} ({result['error']})")

    print("\n5) Frische DB: Kursverlauf einspielen und Outcomes auswerten…")
    session.close()
    session = _demo_session()
    append_entry(session, entry_type="signal", ticker="AAPL",
                 payload={"signal_type": "breakout", "entry": 100.0, "stop": 95.0,
                          "target": 110.0, "horizon_days": 20},
                 price_at_creation=100.0, probability=0.65, ts_utc=base_day)
    append_entry(session, entry_type="signal", ticker="AAPL",
                 payload={"signal_type": "mean_reversion", "entry": 100.0, "stop": 96.0,
                          "target": 108.0, "horizon_days": 20},
                 price_at_creation=100.0, probability=0.55,
                 ts_utc=base_day + timedelta(hours=1))
    # Kurs läuft erst auf 111 (Ziel Signal 1 erreicht), fällt dann auf 95 (Stop Signal 2)
    closes = [102.0, 105.0, 111.0, 104.0, 99.0, 95.5]
    bars = [
        PriceBar(ticker="AAPL", date=date(2026, 6, 2) + timedelta(days=i),
                 open=c, high=c + 1.0, low=c - 1.0, close=c, adj_close=c, volume=1e6)
        for i, c in enumerate(closes)
    ]
    upsert_price_bars(session, bars)
    summary = evaluate_open_signals(session, as_of=date(2026, 6, 30))
    session.commit()
    print(f"   Auswertung: {summary}")
    for stat in stats_by_signal_type(session):
        print(f"   {stat['signal_type']:<16} n={stat['n_signals']} "
              f"geschlossen={stat['n_closed']} Hit-Rate={stat['hit_rate']} "
              f"Ø-Rendite={stat['avg_return_pct']}% Brier={stat['brier']} "
              f"[{stat['calibration']['label']}]")

    print("\n6) Kette nach Outcome-Einträgen erneut verifizieren:")
    print(f"   {verify_chain(session)}")
    session.close()
    print("\nDemo-DB: data/ledger_demo.db (Wegwerf-Sandbox, nicht das echte Ledger)")


if __name__ == "__main__":
    main()
