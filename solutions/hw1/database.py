"""Small, durable SQLite repository. All SQL values are parameterized."""
import json
import sqlite3
from contextlib import contextmanager


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path):
    with connect(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY,
                source_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                authors TEXT NOT NULL DEFAULT '[]',
                year INTEGER,
                abstract TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                pdf_path TEXT,
                pages TEXT NOT NULL DEFAULT '[]',
                metadata_method TEXT NOT NULL DEFAULT 'arXiv API',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY,
                paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                question TEXT NOT NULL DEFAULT '',
                answer TEXT NOT NULL,
                model TEXT NOT NULL,
                sources TEXT NOT NULL,
                coverage TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)


def paper_dict(row, full=False):
    paper = dict(row)
    paper['authors'] = json.loads(paper['authors'])
    pages = json.loads(paper.pop('pages'))
    paper['page_count'] = len(pages)
    paper['has_full_text'] = bool(pages)
    paper['has_pdf'] = bool(paper.pop('pdf_path'))
    if full:
        paper['pages'] = pages
    return paper
