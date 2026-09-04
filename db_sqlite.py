#!/usr/bin/env python3
"""
SQLite + local embeddings fallback for development/testing.
Production should use PostgreSQL + pgvector (see db_setup.sql).
"""
import sqlite3
import json
import os
import uuid
from pathlib import Path
from datetime import datetime
import numpy as np

# For production, use: from openai import OpenAI
# For local dev, use sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDER = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dim, fast, local
    EMBED_DIM = 384
    USE_LOCAL = True
except ImportError:
    EMBEDDER = None
    EMBED_DIM = 1536
    USE_LOCAL = False
    print("Warning: sentence-transformers not installed, embeddings will be random")

DB_PATH = Path(__file__).parent / "papers.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id TEXT PRIMARY KEY,
            source_pdf TEXT,
            title TEXT,
            authors TEXT,
            journal TEXT,
            year INTEGER,
            doi TEXT,
            keywords TEXT,
            research TEXT,
            states TEXT,
            theory TEXT,
            numerical TEXT,
            observables TEXT,
            results TEXT,
            figures TEXT,
            equations TEXT,
            limitations TEXT,
            refs TEXT,
            embedding BLOB,
            full_text TEXT,
            meta TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # FTS5 virtual table for full-text search
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
            title, research_question, method, observables, results, content='papers', content_rowid='rowid'
        )
    """)
    conn.commit()
    return conn


def get_embedding(text: str) -> np.ndarray:
    if USE_LOCAL and EMBEDDER:
        return EMBEDDER.encode(text[:8000]).astype(np.float32)
    # Fallback: deterministic pseudo-random for dev
    np.random.seed(hash(text) % 2**32)
    return np.random.randn(EMBED_DIM).astype(np.float32)


def build_full_text(paper: dict) -> str:
    parts = []
    p = paper.get("paper", {})
    r = paper.get("research", {})
    t = paper.get("theory", {})
    if p.get("title"): parts.append(p["title"])
    if r.get("research_question"): parts.append(r["research_question"])
    if t.get("method"): parts.append(t["method"])
    for obs in paper.get("observables", []):
        if isinstance(obs, dict) and obs.get("name"): parts.append(obs["name"])
    for res in paper.get("results", []):
        if isinstance(res, dict):
            for k in ["key_features", "finding", "agreement"]:
                if res.get(k): parts.append(str(res[k]))
    return " ".join(parts)


def ingest_json(json_path: str):
    with open(json_path) as f:
        paper = json.load(f)

    conn = init_db()
    cur = conn.cursor()

    paper_id = str(uuid.uuid4())
    p = paper.get("paper", {})
    r = paper.get("research", {})
    s = paper.get("states", {})
    t = paper.get("theory", {})
    n = paper.get("numerical", {})

    full_text = build_full_text(paper)
    embedding = get_embedding(full_text)

    cur.execute("""
        INSERT INTO papers (id, source_pdf, title, authors, journal, year, doi, keywords,
            research, states, theory, numerical, observables, results,
            figures, equations, limitations, refs,
            embedding, full_text, meta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        paper_id,
        paper.get("metadata", {}).get("source_pdf", Path(json_path).stem + ".pdf"),
        p.get("title"),
        json.dumps(p.get("authors", []), ensure_ascii=False),
        p.get("journal"),
        p.get("year"),
        p.get("doi"),
        json.dumps(p.get("keywords", []), ensure_ascii=False),
        json.dumps(r, ensure_ascii=False), json.dumps(s, ensure_ascii=False),
        json.dumps(t, ensure_ascii=False), json.dumps(n, ensure_ascii=False),
        json.dumps(paper.get("observables", []), ensure_ascii=False),
        json.dumps(paper.get("results", []), ensure_ascii=False),
        json.dumps(paper.get("figures", []), ensure_ascii=False),
        json.dumps(paper.get("equations", []), ensure_ascii=False),
        json.dumps(paper.get("limitations", []), ensure_ascii=False),
        json.dumps(paper.get("references", []), ensure_ascii=False),
        embedding.tobytes(),
        full_text,
        json.dumps(paper.get("metadata", {}), ensure_ascii=False)
    ))

    # Update FTS
    cur.execute("""
        INSERT INTO papers_fts (rowid, title, research_question, method, observables, results)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        cur.lastrowid,
        p.get("title", ""),
        r.get("research_question", "") if isinstance(r, dict) else "",
        t.get("method", "") if isinstance(t, dict) else "",
        " ".join([obs.get("name", "") for obs in paper.get("observables", []) if isinstance(obs, dict)]),
        " ".join([str(res.get(k, "")) for res in paper.get("results", []) if isinstance(res, dict) for k in ["key_features", "finding", "agreement"]])
    ))

    conn.commit()
    conn.close()
    print(f"✓ Ingested {paper_id[:8]}: {p.get('title', '')[:60]}")


def search(query: str, top_k: int = 5):
    """Hybrid search: FTS + vector similarity."""
    conn = init_db()
    cur = conn.cursor()

    # FTS search - escape special chars
    fts_query = query.replace('-', ' ').replace('"', '')
    cur.execute("""
        SELECT p.id, p.title, p.year, p.research, p.theory, p.observables, p.results,
               bm25(papers_fts) as bm25_score
        FROM papers p
        JOIN papers_fts ON p.rowid = papers_fts.rowid
        WHERE papers_fts MATCH ?
        ORDER BY bm25_score
        LIMIT ?
    """, (fts_query, top_k * 2))
    fts_results = cur.fetchall()

    # Vector search (if we have embeddings)
    q_emb = get_embedding(query)
    cur.execute("SELECT id, title, year, research, theory, observables, results, embedding FROM papers")
    all_papers = cur.fetchall()

    vec_scores = []
    for row in all_papers:
        emb_bytes = row[7]
        if emb_bytes:
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            sim = np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb) + 1e-8)
            vec_scores.append((row[0], sim))

    vec_scores.sort(key=lambda x: x[1], reverse=True)
    vec_top = vec_scores[:top_k]

    # Combine (simple reciprocal rank fusion)
    combined = {}
    for rank, (pid, _) in enumerate([(r[0], 0) for r in fts_results]):
        combined[pid] = combined.get(pid, 0) + 1.0 / (rank + 1 + 60)
    for rank, (pid, score) in enumerate(vec_top):
        combined[pid] = combined.get(pid, 0) + 1.0 / (rank + 1 + 60)

    # Get full records for top results
    top_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)[:top_k]
    placeholders = ",".join("?" * len(top_ids))
    cur.execute(f"SELECT id, title, year, research, theory, observables, results FROM papers WHERE id IN ({placeholders})", top_ids)
    results = cur.fetchall()

    conn.close()
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python db_sqlite.py <json_path> [json_path...]")
        print("       python db_sqlite.py --search 'query'")
        sys.exit(1)

    if sys.argv[1] == "--search":
        query = " ".join(sys.argv[2:])
        results = search(query)
        for r in results:
            print(f"\n--- {r[0][:8]} | {r[1][:60]} ({r[2]}) ---")
            research = json.loads(r[3]) if r[3] else {}
            theory = json.loads(r[4]) if r[4] else {}
            print(f"Research: {research.get('research_question', research.get('objective', ''))[:120]}")
            print(f"Method: {theory.get('method', theory.get('framework', ''))[:120]}")
    else:
        for json_path in sys.argv[1:]:
            ingest_json(json_path)