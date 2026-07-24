"""SQLite persistence for the dabic self-improving run.

Records every judge submission (score + full A-F breakdown), tracks the
best-across-submissions champion (EdgeBench's selection rule), and holds the
rolling `lessons` summary that keeps 24/7 context bounded.
"""
import json
import time
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, turn INTEGER, score REAL,
                A REAL, B REAL, C REAL, D REAL, E REAL, F REAL,
                summary TEXT, result_json TEXT, snapshot_dir TEXT
            );
            CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT);
            """
        )
        self.db.commit()

    def add_submission(self, *, turn, result: dict, snapshot_dir: str = "") -> int:
        comp = {}
        for d in result.get("details", []):
            name = (d.get("name", "") or "")[:1].upper()  # A_static -> A
            msg = d.get("message", "")
            # pull "score=X/Y" if present
            comp[name] = d.get("score")
        def g(k):
            v = comp.get(k)
            return float(v) if isinstance(v, (int, float)) else None
        cur = self.db.execute(
            "INSERT INTO submissions (ts,turn,score,A,B,C,D,E,F,summary,result_json,snapshot_dir) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), turn, float(result.get("score", 0.0)),
             g("A"), g("B"), g("C"), g("D"), g("E"), g("F"),
             result.get("summary", ""), json.dumps(result), snapshot_dir),
        )
        self.db.commit()
        return cur.lastrowid

    def best(self):
        return self.db.execute(
            "SELECT * FROM submissions ORDER BY score DESC, id ASC LIMIT 1"
        ).fetchone()

    def recent(self, limit=8):
        return self.db.execute(
            "SELECT * FROM submissions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def count(self):
        return self.db.execute("SELECT COUNT(*) c FROM submissions").fetchone()["c"]

    def curve(self):
        rows = self.db.execute("SELECT id, score FROM submissions ORDER BY id").fetchall()
        out, best = [], -1.0
        for r in rows:
            best = max(best, r["score"])
            out.append((r["id"], r["score"], best))
        return out

    def set_lessons(self, text):
        self.db.execute("DELETE FROM lessons")
        self.db.execute("INSERT INTO lessons (text) VALUES (?)", (text,))
        self.db.commit()

    def get_lessons(self):
        row = self.db.execute("SELECT text FROM lessons ORDER BY id DESC LIMIT 1").fetchone()
        return row["text"] if row else ""
