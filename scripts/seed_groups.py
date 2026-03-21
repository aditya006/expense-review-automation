#!/usr/bin/env python3
from __future__ import annotations

import json

from app.db import SessionLocal, init_db
from app.models import GroupCache


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        demo_groups = [
            GroupCache(
                group_id="g1",
                group_name="Goa Trip",
                members_json=json.dumps(["u1", "u2", "u3"]),
            ),
            GroupCache(
                group_id="g2",
                group_name="Flatmates",
                members_json=json.dumps(["u1", "u4"]),
            ),
        ]
        for group in demo_groups:
            db.merge(group)
        db.commit()
        print("Seeded groups")
    finally:
        db.close()


if __name__ == "__main__":
    main()
