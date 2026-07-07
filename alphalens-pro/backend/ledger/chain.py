"""Hash-Chain-Kern des Track-Record-Ledgers (USP 3).

Jeder Eintrag hasht seinen kompletten Fachinhalt PLUS den Hash des Vorgängers.
Nachträgliches Ändern irgendeines Feldes irgendeines Eintrags macht dessen Hash
ungültig und reißt damit die gesamte Kette dahinter ab — verify_chain() findet
die erste gebrochene Stelle. Ergebnisse und Korrekturen sind neue Einträge."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import LedgerEntry

GENESIS_HASH = "0" * 64

ENTRY_TYPES = ("signal", "pick", "outcome", "correction", "note")


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministische Serialisierung — Grundlage der Hash-Reproduzierbarkeit."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(
    prev_hash: str,
    ts_utc: datetime,
    entry_type: str,
    ticker: str,
    payload_json: str,
    price_at_creation: float | None,
    probability: float | None,
    ref_id: int | None,
) -> str:
    """SHA-256 über prev_hash + alle Fachfelder in fixer Reihenfolge und Formatierung.
    Diese Funktion ist der EINZIGE Ort, an dem das Hash-Format definiert ist —
    append und verify benutzen sie beide."""
    material = "|".join([
        prev_hash,
        ts_utc.isoformat(),
        entry_type,
        ticker,
        payload_json,
        "" if price_at_creation is None else repr(price_at_creation),
        "" if probability is None else repr(probability),
        "" if ref_id is None else str(ref_id),
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def last_entry(session: Session) -> LedgerEntry | None:
    return session.scalar(select(LedgerEntry).order_by(LedgerEntry.id.desc()).limit(1))


def append_entry(
    session: Session,
    *,
    entry_type: str,
    ticker: str,
    payload: dict[str, Any],
    price_at_creation: float | None = None,
    probability: float | None = None,
    ref_id: int | None = None,
    ts_utc: datetime | None = None,
) -> LedgerEntry:
    """Einzige Schreiboperation des Ledgers. Verkettet mit dem letzten Eintrag."""
    if entry_type not in ENTRY_TYPES:
        raise ValueError(f"Unbekannter entry_type {entry_type!r} (erlaubt: {ENTRY_TYPES})")
    if probability is not None and not (0.0 <= probability <= 1.0):
        raise ValueError(f"probability muss in [0, 1] liegen, war {probability}")
    ts = ts_utc or datetime.utcnow()
    payload_json = canonical_json(payload)
    prev = last_entry(session)
    prev_hash = prev.entry_hash if prev is not None else GENESIS_HASH
    entry = LedgerEntry(
        ts_utc=ts,
        entry_type=entry_type,
        ticker=ticker,
        payload_json=payload_json,
        price_at_creation=price_at_creation,
        probability=probability,
        ref_id=ref_id,
        prev_hash=prev_hash,
        entry_hash=compute_entry_hash(
            prev_hash, ts, entry_type, ticker, payload_json,
            price_at_creation, probability, ref_id,
        ),
    )
    session.add(entry)
    session.flush()  # id sofort vergeben — Outcomes referenzieren darüber
    return entry


def verify_chain(session: Session) -> dict[str, Any]:
    """Rechnet die komplette Kette nach. Findet Manipulationen auch dann, wenn
    die Append-only-Trigger entfernt und Zeilen direkt geändert wurden."""
    entries = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.id)))
    expected_prev = GENESIS_HASH
    for entry in entries:
        if entry.prev_hash != expected_prev:
            return {"valid": False, "entries": len(entries), "first_broken_id": entry.id,
                    "error": "prev_hash-Verkettung gebrochen"}
        recomputed = compute_entry_hash(
            entry.prev_hash, entry.ts_utc, entry.entry_type, entry.ticker,
            entry.payload_json, entry.price_at_creation, entry.probability, entry.ref_id,
        )
        if recomputed != entry.entry_hash:
            return {"valid": False, "entries": len(entries), "first_broken_id": entry.id,
                    "error": "entry_hash stimmt nicht mit Inhalt überein (Manipulation)"}
        expected_prev = entry.entry_hash
    return {"valid": True, "entries": len(entries), "first_broken_id": None, "error": None}


def entry_payload(entry: LedgerEntry) -> dict[str, Any]:
    data = json.loads(entry.payload_json)
    if not isinstance(data, dict):
        raise ValueError(f"Ledger-Payload von #{entry.id} ist kein Objekt")
    return data
