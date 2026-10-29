#!/usr/bin/env python3
"""
ForgeWorks Factory Management System — Direct SQLite Database Inspector
Run this script anytime to see the actual tables and records stored in factory.db:
    python view_database.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("factory.db")

def inspect_database():
    if not DB_PATH.exists():
        print(f"Database file not found at: {DB_PATH.resolve()}")
        return

    print("=" * 80)
    print(f"ACTUAL SQLITE DATABASE: {DB_PATH.resolve()}")
    print(f"DATABASE FILE SIZE: {DB_PATH.stat().st_size:,} bytes")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%' 
        ORDER BY name
    """).fetchall()

    print(f"\nTOTAL TABLES FOUND: {len(tables)}\n")

    for t in tables:
        table_name = t["name"]
        rows = cursor.execute(f"SELECT * FROM {table_name}").fetchall()
        col_info = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c["name"] for c in col_info]
        pk_cols = [c["name"] for c in col_info if c["pk"]]

        print(f"+-- TABLE: {table_name.upper()} ({len(rows)} records) " + "-" * 40)
        print(f"| Primary Key: {', '.join(pk_cols) if pk_cols else 'None'}")
        print(f"| Columns: {', '.join(cols)}")
        print("+" + "-" * 78)

        if not rows:
            print("| (Table is empty)")
        else:
            display_cols = cols
            widths = [len(c) for c in display_cols]
            sample_rows = rows[:12]
            for r in sample_rows:
                for i, c in enumerate(display_cols):
                    val_str = str(r[c] if r[c] is not None else "NULL")
                    widths[i] = min(30, max(widths[i], len(val_str)))

            header = " | ".join(c.ljust(widths[i])[:widths[i]] for i, c in enumerate(display_cols))
            sep = "-+-".join("-" * widths[i] for i in range(len(widths)))
            print(f"| {header}")
            print(f"| {sep}")

            for r in sample_rows:
                row_str = " | ".join(str(r[c] if r[c] is not None else "NULL").ljust(widths[i])[:widths[i]] for i, c in enumerate(display_cols))
                print(f"| {row_str}")

            if len(rows) > 12:
                print(f"| ... and {len(rows) - 12} more records")

        print("+" + "-" * 78 + "\n")

    conn.close()

if __name__ == "__main__":
    inspect_database()
