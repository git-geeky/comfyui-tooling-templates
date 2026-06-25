#!/usr/bin/env python3
"""Generic preference-lab helpers for ComfyUI-style output review."""

from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from . import local_restore
except ImportError:
    import local_restore  # type: ignore


SCHEMA_VERSION = "preference-lab-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, Mapping):
        raise ValueError("metadata JSON must be an object")
    return dict(payload)


def default_db_path() -> Path:
    restore = local_restore.load_restore_config()
    paths = restore.get("paths", {}) if isinstance(restore, Mapping) else {}
    value = paths.get("preference_lab_db") if isinstance(paths, Mapping) else None
    if value:
        return Path(str(value)).expanduser()
    return Path("out") / "preference-lab.sqlite"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS preference_lab_schema (
            component TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS preference_items (
            item_id TEXT PRIMARY KEY,
            source_path TEXT,
            prompt TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS preference_ratings (
            rating_id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL REFERENCES preference_items(item_id) ON DELETE CASCADE,
            score REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
            reviewer TEXT NOT NULL DEFAULT 'local',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS preference_comparisons (
            comparison_id TEXT PRIMARY KEY,
            left_item_id TEXT NOT NULL REFERENCES preference_items(item_id) ON DELETE CASCADE,
            right_item_id TEXT NOT NULL REFERENCES preference_items(item_id) ON DELETE CASCADE,
            winner_item_id TEXT REFERENCES preference_items(item_id) ON DELETE CASCADE,
            reviewer TEXT NOT NULL DEFAULT 'local',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            CHECK (left_item_id <> right_item_id),
            CHECK (winner_item_id IS NULL OR winner_item_id IN (left_item_id, right_item_id))
        );
        """
    )
    conn.execute(
        """
        INSERT INTO preference_lab_schema(component, version, updated_at)
        VALUES('preference_lab', ?, ?)
        ON CONFLICT(component) DO UPDATE SET
            version=excluded.version,
            updated_at=excluded.updated_at
        """,
        (SCHEMA_VERSION, utc_now()),
    )
    conn.commit()


def add_item(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    source_path: str = "",
    prompt: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    init_db(conn)
    conn.execute(
        """
        INSERT INTO preference_items(item_id, source_path, prompt, metadata_json, created_at)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(item_id) DO UPDATE SET
            source_path=excluded.source_path,
            prompt=excluded.prompt,
            metadata_json=excluded.metadata_json
        """,
        (item_id, source_path, prompt, json_dumps(dict(metadata or {})), utc_now()),
    )
    conn.commit()


def record_rating(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    score: float,
    reviewer: str = "local",
    notes: str = "",
) -> str:
    init_db(conn)
    rating_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO preference_ratings(rating_id, item_id, score, reviewer, notes, created_at)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (rating_id, item_id, float(score), reviewer, notes, utc_now()),
    )
    conn.commit()
    return rating_id


def record_comparison(
    conn: sqlite3.Connection,
    *,
    left_item_id: str,
    right_item_id: str,
    winner: str | None,
    reviewer: str = "local",
    notes: str = "",
) -> str:
    init_db(conn)
    winner_item_id = None
    if winner == "left":
        winner_item_id = left_item_id
    elif winner == "right":
        winner_item_id = right_item_id
    elif winner not in (None, "tie"):
        raise ValueError("winner must be left, right, tie, or None")
    comparison_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO preference_comparisons(
            comparison_id, left_item_id, right_item_id, winner_item_id, reviewer, notes, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (comparison_id, left_item_id, right_item_id, winner_item_id, reviewer, notes, utc_now()),
    )
    conn.commit()
    return comparison_id


def summary(conn: sqlite3.Connection) -> dict[str, Any]:
    init_db(conn)
    item_count = conn.execute("SELECT COUNT(*) AS count FROM preference_items").fetchone()["count"]
    rating_count = conn.execute("SELECT COUNT(*) AS count FROM preference_ratings").fetchone()["count"]
    comparison_count = conn.execute("SELECT COUNT(*) AS count FROM preference_comparisons").fetchone()["count"]
    rows = conn.execute(
        """
        SELECT i.item_id, COUNT(r.rating_id) AS rating_count, AVG(r.score) AS average_score
        FROM preference_items i
        LEFT JOIN preference_ratings r ON r.item_id = i.item_id
        GROUP BY i.item_id
        ORDER BY average_score DESC NULLS LAST, i.item_id ASC
        """
    ).fetchall()
    return {
        "schema_version": SCHEMA_VERSION,
        "items": item_count,
        "ratings": rating_count,
        "comparisons": comparison_count,
        "ranked_items": [
            {
                "item_id": row["item_id"],
                "rating_count": row["rating_count"],
                "average_score": row["average_score"],
            }
            for row in rows
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a generic preference-lab SQLite database.")
    parser.add_argument("--db", default=None, help="SQLite database path. Defaults to restore overlay or out/.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize the database schema.")

    add = subparsers.add_parser("add-item", help="Add or update an item.")
    add.add_argument("--item-id", required=True)
    add.add_argument("--source-path", default="")
    add.add_argument("--prompt", default="")
    add.add_argument("--metadata-json", default=None)

    rate = subparsers.add_parser("rate", help="Record a scalar rating between 0 and 1.")
    rate.add_argument("--item-id", required=True)
    rate.add_argument("--score", required=True, type=float)
    rate.add_argument("--reviewer", default="local")
    rate.add_argument("--notes", default="")

    compare = subparsers.add_parser("compare", help="Record a pairwise comparison.")
    compare.add_argument("--left", required=True)
    compare.add_argument("--right", required=True)
    compare.add_argument("--winner", choices=["left", "right", "tie"], default="tie")
    compare.add_argument("--reviewer", default="local")
    compare.add_argument("--notes", default="")

    subparsers.add_parser("summary", help="Print summary JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db).expanduser() if args.db else default_db_path()
    conn = connect(db_path)
    try:
        if args.command == "init":
            init_db(conn)
            print(json_dumps({"db": str(db_path), "schema_version": SCHEMA_VERSION}))
        elif args.command == "add-item":
            add_item(
                conn,
                item_id=args.item_id,
                source_path=args.source_path,
                prompt=args.prompt,
                metadata=parse_json_object(args.metadata_json),
            )
            print(json_dumps({"item_id": args.item_id, "status": "upserted"}))
        elif args.command == "rate":
            rating_id = record_rating(
                conn,
                item_id=args.item_id,
                score=args.score,
                reviewer=args.reviewer,
                notes=args.notes,
            )
            print(json_dumps({"rating_id": rating_id, "status": "recorded"}))
        elif args.command == "compare":
            comparison_id = record_comparison(
                conn,
                left_item_id=args.left,
                right_item_id=args.right,
                winner=args.winner,
                reviewer=args.reviewer,
                notes=args.notes,
            )
            print(json_dumps({"comparison_id": comparison_id, "status": "recorded"}))
        elif args.command == "summary":
            print(json.dumps(summary(conn), indent=2, ensure_ascii=True, sort_keys=True))
        else:
            parser.error(f"unknown command: {args.command}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

