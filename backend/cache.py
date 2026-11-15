import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

DB_PATH = Path(__file__).parent / "assistant_state.db"
ARG_PATTERN = re.compile(r'("[^"]+"|\'[^\']+\'|[A-Za-z]:\\[^\s"\']+)')


def normalize_intent(prompt: str) -> Tuple[str, List[str]]:
    """Replaces literal paths/quoted values with {arg0}, {arg1} placeholders."""
    args: List[str] = []

    def _repl(match: re.Match) -> str:
        idx = len(args)
        args.append(match.group(0))
        return f"{{arg{idx}}}"

    template_key = ARG_PATTERN.sub(_repl, prompt.strip().lower())
    return template_key, args


class StateStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_cache (
                    template_key TEXT PRIMARY KEY,
                    cmd_template TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    tier INTEGER NOT NULL,
                    intent TEXT NOT NULL,
                    command TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL
                )
                """
            )

    def lookup_cached_command(self, prompt: str) -> Optional[str]:
        template_key, args = normalize_intent(prompt)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cmd_template FROM plan_cache WHERE template_key = ?",
                (template_key,),
            ).fetchone()
        if not row:
            return None
        cmd_template = row[0]
        for idx, val in enumerate(args):
            cmd_template = cmd_template.replace(f"{{arg{idx}}}", val)
        return cmd_template

    def store_cached_command(self, prompt: str, executed_command: str):
        template_key, args = normalize_intent(prompt)
        cmd_template = executed_command
        for idx, val in enumerate(args):
            if val in cmd_template:
                cmd_template = cmd_template.replace(val, f"{{arg{idx}}}", 1)
            else:
                return  # Skip caching if argument mapping is ambiguous
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO plan_cache (template_key, cmd_template) VALUES (?, ?)",
                (template_key, cmd_template),
            )

    def append_audit(
        self, workflow: str, tier: int, intent: str, command: str, status: str
    ):
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            last = conn.execute(
                "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = last[0] if last else "GENESIS"
            payload = f"{prev_hash}|{ts}|{workflow}|{tier}|{intent}|{command}|{status}"
            entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            conn.execute(
                """
                INSERT INTO audit_log
                (timestamp, workflow, tier, intent, command, status, prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, workflow, tier, intent, command, status, prev_hash, entry_hash),
            )