"""Meilenstein-2-Demo: Scores berechnen und Breakdown für Referenz-Ticker zeigen.

    python -m backend.scoring.demo AAPL SAP.DE VWCE.DE
(Erwartet gefüllte Kurs-/Fundamentaldaten — vorher `make demo` oder `make update`.)"""

from __future__ import annotations

import argparse
import logging

from backend.db import session_scope
from backend.scoring.engine import compute_scores, score_breakdown


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="AlphaLens Pro — Scoring-Demo")
    parser.add_argument("tickers", nargs="*", default=["AAPL", "SAP.DE", "VWCE.DE"])
    args = parser.parse_args()
    tickers = args.tickers or ["AAPL", "SAP.DE", "VWCE.DE"]

    with session_scope() as session:
        summary = compute_scores(session)
        print(f"Scoring-Lauf: {summary}\n")
        for ticker in tickers:
            breakdown = score_breakdown(session, ticker)
            if breakdown is None:
                print(f"=== {ticker}: keine Scores (nicht im Universum?)\n")
                continue
            print(f"=== {ticker}  (Stichtag {breakdown['date']}) ===")
            if breakdown["composite"] is not None:
                print(f"  Composite Score: {breakdown['composite']:>5.1f} / 100")
            print(f"  Risiko-Score:    {breakdown['risk_score']:>5.1f} / 10   "
                  f"[{breakdown['risk_detail']}]")
            for pillar in breakdown["pillars"]:
                flag = " (alle Komponenten fehlend -> neutral)" if pillar["missing"] else ""
                print(f"  {pillar['name']:<10} {pillar['score']:>5.1f}  "
                      f"(Gewicht {pillar['weight']:.0%}){flag}")
                for c in pillar["components"]:
                    marker = "~" if c["missing"] else " "
                    print(f"    {marker} {c['name'].split('.', 1)[1]:<20} {c['score']:>5.1f}  "
                          f"{c['detail']}")
            print()


if __name__ == "__main__":
    main()
