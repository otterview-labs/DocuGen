#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration: Alter rag_contents.file_transaction to TEXT/LONGTEXT

Idempotent migration that checks if the column exists and, if so, changes its
type to a text-capable type to avoid "Data too long" errors in MySQL.
"""

from typing import Optional
from sqlalchemy import text, inspect


def migrate(engine) -> Optional[str]:
    """Run the migration if applicable.

    Returns a short status string or None when skipped.
    """
    try:
        insp = inspect(engine)
        if 'rag_contents' not in insp.get_table_names():
            return 'rag_contents table not found; skipped'

        cols = {c['name']: c for c in insp.get_columns('rag_contents')}
        if 'file_transaction' not in cols:
            return "column 'file_transaction' not present; skipped"

        dialect = engine.dialect.name.lower()
        with engine.begin() as conn:
            if dialect == 'mysql':
                # Use LONGTEXT to be safe for large data
                conn.execute(text("ALTER TABLE rag_contents MODIFY COLUMN file_transaction LONGTEXT"))
                return 'mysql: altered to LONGTEXT'
            elif dialect in ('postgresql', 'postgres'):
                conn.execute(text("ALTER TABLE rag_contents ALTER COLUMN file_transaction TYPE TEXT"))
                return 'postgres: altered to TEXT'
            elif dialect == 'sqlite':
                # SQLite does not support altering column types directly without table rebuild.
                # Skip here to avoid destructive operations.
                return 'sqlite: cannot alter column type non-destructively; skipped'
            else:
                return f'{dialect}: unsupported dialect; skipped'
    except Exception as e:
        # Return error string so caller can log it
        return f'error: {e}'
