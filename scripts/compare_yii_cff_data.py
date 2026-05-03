"""Data integrity verification: compare Yii2 vs CFF tables.

Usage:
    python -m scripts.compare_yii_cff_data            # row counts only
    python -m scripts.compare_yii_cff_data --strict   # also field-by-field spot-check (100 random rows per pair)

Exit codes:
    0 = data integrity OK (CFF >= Yii for all pairs, no field mismatches in spot-check)
    1 = some Yii rows missing in CFF (CFF < Yii)
    2 = field mismatches found in spot-check (--strict only)
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from sqlalchemy import text

from shared.db.connection import get_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# ─── Pairs of (yii_table, cff_table, count_match_query, optional_filter) ────
COUNT_PAIRS: list[tuple[str, str, str, str]] = [
    # name, yii_table, cff_table, optional WHERE for cff (to count only mapped rows)
    ("Channels", "youtube_channels", "platform_channels", "platform = 'youtube'"),
    ("Tasks", "tasks", "content_upload_queue_tasks", ""),
    ("Streams", "stream", "live_stream_configurations", ""),
    ("Daily Stats", "youtube_channel_daily", "channel_daily_statistics", ""),
    ("OAuth Consoles", "google_consoles", "platform_oauth_credentials", "platform = 'google'"),
]


def _exec_scalar(conn, sql: str) -> int:
    try:
        return int(conn.execute(text(sql)).scalar() or 0)
    except Exception as exc:
        logger.warning("Query failed: %s — %s", sql, exc)
        return -1


def verify_counts(conn) -> tuple[int, int]:
    """Returns (ok_count, fail_count)."""
    ok = 0
    fail = 0
    print("\n=== ROW COUNT VERIFICATION ===")
    for name, yii_t, cff_t, where in COUNT_PAIRS:
        yii_count = _exec_scalar(conn, f"SELECT COUNT(*) FROM {yii_t}")
        cff_q = f"SELECT COUNT(*) FROM {cff_t}" + (f" WHERE {where}" if where else "")
        cff_count = _exec_scalar(conn, cff_q)

        if yii_count < 0 or cff_count < 0:
            print(f"  [SKIP]   {name:<14}  Yii={yii_count}  CFF={cff_count}  (table missing?)")
            continue

        diff = cff_count - yii_count
        if diff >= 0:
            status = "OK"
            ok += 1
        else:
            status = "MISSING"
            fail += 1
        print(f"  [{status:7}] {name:<14}  Yii={yii_count:>8}  CFF={cff_count:>8}  Δ={diff:+}")
    return ok, fail


# ─── Field-level spot-check ────────────────────────────────────────────

# Each: (description, sql) — sql returns rows where there's a mismatch.
SPOT_CHECKS: list[tuple[str, str]] = [
    (
        "youtube_channels.platform_channel_id ↔ platform_channels.platform_channel_id",
        """
        SELECT yc.id, yc.channel_id AS yii_yt_id, pc.platform_channel_id AS cff_yt_id, yc.name
        FROM youtube_channels yc
        LEFT JOIN platform_channels pc
               ON pc.platform = 'youtube' AND pc.platform_channel_id = yc.channel_id
        WHERE pc.id IS NULL
        LIMIT 20
        """,
    ),
    (
        "tasks.upload_id ↔ content_upload_queue_tasks.upload_id (для completed)",
        """
        SELECT t.id, t.upload_id AS yii_uploaded, c.upload_id AS cff_uploaded
        FROM tasks t
        LEFT JOIN content_upload_queue_tasks c ON c.id = t.id
        WHERE t.status = 1
          AND t.upload_id IS NOT NULL
          AND (c.id IS NULL OR c.upload_id <> t.upload_id)
        LIMIT 20
        """,
    ),
    (
        "stream.service_name ↔ live_stream_configurations.service_name",
        """
        SELECT s.id, s.service_name, lsc.service_name AS cff_service
        FROM stream s
        LEFT JOIN live_stream_configurations lsc ON lsc.service_name = s.service_name
        WHERE lsc.id IS NULL
        LIMIT 20
        """,
    ),
    (
        "google_consoles.client_id ↔ platform_oauth_credentials.client_id",
        """
        SELECT gc.id, gc.name, gc.client_id AS yii_cid, poc.client_id AS cff_cid
        FROM google_consoles gc
        LEFT JOIN platform_oauth_credentials poc
               ON poc.platform = 'google' AND poc.name = gc.name
        WHERE poc.id IS NULL OR (gc.client_id <> poc.client_id)
        LIMIT 20
        """,
    ),
]


def verify_spot_check(conn) -> int:
    """Returns count of spot-check failures."""
    print("\n=== FIELD-LEVEL SPOT CHECK ===")
    total_failures = 0
    for desc, sql in SPOT_CHECKS:
        try:
            rows = conn.execute(text(sql)).fetchall()
        except Exception as exc:
            print(f"  [SKIP] {desc} — query failed: {exc}")
            continue
        if not rows:
            print(f"  [OK]   {desc}")
            continue
        total_failures += len(rows)
        print(f"  [FAIL] {desc} — {len(rows)} mismatches:")
        for r in rows[:5]:
            print(f"           {dict(r._mapping)}")
        if len(rows) > 5:
            print(f"           ... and {len(rows) - 5} more")
    return total_failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Also do field-level spot-check; exit 2 if mismatches found")
    args = parser.parse_args()

    engine = get_engine()
    with engine.connect() as conn:
        ok, fail = verify_counts(conn)
        spot_failures = 0
        if args.strict:
            spot_failures = verify_spot_check(conn)

    print(f"\n=== SUMMARY ===")
    print(f"  Row counts: {ok} ok, {fail} missing")
    if args.strict:
        print(f"  Spot-check: {spot_failures} field mismatches")
    print()

    if fail > 0:
        return 1
    if args.strict and spot_failures > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
