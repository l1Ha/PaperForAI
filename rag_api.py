#!/usr/bin/env python3
"""
FastAPI RAG service for quantum collision literature.
Run: uvicorn rag_api:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
import sqlite3
import numpy as np
from pathlib import Path

# Local embedder (dev)
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDER = SentenceTransformer('all-MiniLM-L6-v2')
    USE_LOCAL = True
except ImportError:
    EMBEDDER = None
    USE_LOCAL = False

DB_PATH = Path(__file__).parent / "papers.db"
EMBED_DIM = 384 if USE_LOCAL else 1536


def get_embedding(text: str) -> np.ndarray:
    if USE_LOCAL and EMBEDDER:
        return EMBEDDER.encode(text[:8000]).astype(np.float32)
    np.random.seed(hash(text) % 2**32)
    return np.random.randn(EMBED_DIM).astype(np.float32)


def normalize_json_field(field, key_map=None):
    """Normalize field that could be dict or list to dict."""
    if isinstance(field, dict):
        return field
    elif isinstance(field, list):
        return {str(i): (v.get(key_map, "") if isinstance(v, dict) and key_map else v)
                for i, v in enumerate(field)}
    return {}


def search_papers(query: str, top_k: int = 5, filters: dict = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # FTS search
    fts_query = query.replace('-', ' ').replace('"', '')
    cur.execute("""
        SELECT p.id, p.title, p.year, p.research, p.theory, p.observables, p.results, p.figures, p.equations
        FROM papers p
        JOIN papers_fts ON p.rowid = papers_fts.rowid
        WHERE papers_fts MATCH ?
        ORDER BY bm25(papers_fts)
        LIMIT ?
    """, (fts_query, top_k * 3))
    fts_results = cur.fetchall()

    # Vector search
    q_emb = get_embedding(query)
    cur.execute("SELECT id, title, year, research, theory, observables, results, figures, equations, embedding FROM papers")
    all_papers = cur.fetchall()

    vec_scores = []
    for row in all_papers:
        if row[9]:
            emb = np.frombuffer(row[9], dtype=np.float32)
            sim = np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb) + 1e-8)
            vec_scores.append((row[0], sim, row))

    vec_scores.sort(key=lambda x: x[1], reverse=True)

    # RRF fusion
    combined = {}
    for rank, (pid, _, row) in enumerate(vec_scores):
        combined[pid] = combined.get(pid, 0) + 1.0 / (rank + 1 + 60)
    for rank, row in enumerate(fts_results):
        combined[row[0]] = combined.get(row[0], 0) + 1.0 / (rank + 1 + 60)

    top_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)[:top_k]

    # Build response
    results = []
    for pid in top_ids:
        row = next((r for r in all_papers if r[0] == pid), None)
        if not row:
            row = next((r for r in fts_results if r[0] == pid), None)
        if row:
            research = json.loads(row[3]) if row[3] else {}
            theory = json.loads(row[4]) if row[4] else {}
            observables = json.loads(row[5]) if row[5] else []
            results_data = json.loads(row[6]) if row[6] else []
            figures = normalize_json_field(json.loads(row[7]) if row[7] else {}, "description")
            equations = normalize_json_field(json.loads(row[8]) if row[8] else {}, "latex")

            results.append({
                "id": row[0],
                "title": row[1],
                "year": row[2],
                "research_question": research.get("research_question", research.get("objective", "")),
                "system": research.get("system", {}),
                "method": theory.get("method", theory.get("framework", "")),
                "potential": theory.get("potential", {}),
                "observables": [obs.get("name", "") for obs in observables if isinstance(obs, dict)],
                "key_results": [str(res.get(k, "")) for res in results_data if isinstance(res, dict)
                               for k in ["key_features", "finding", "agreement"]],
                "figures": figures,
                "equations": equations,
                "score": combined[pid]
            })

    conn.close()
    return results


# FastAPI app
app = FastAPI(title="Quantum Collision Literature RAG", version="1.0")

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[dict] = None

class QueryResponse(BaseModel):
    query: str
    results: List[dict]
    count: int

@app.post("/search", response_model=QueryResponse)
async def search(req: QueryRequest):
    results = search_papers(req.query, req.top_k, req.filters)
    return {"query": req.query, "results": results, "count": len(results)}

@app.get("/paper/{paper_id}")
async def get_paper(paper_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Paper not found")
    
    return {
        "id": row[0], "source_pdf": row[1], "title": row[2], "authors": json.loads(row[3]),
        "journal": row[4], "year": row[5], "doi": row[6], "keywords": json.loads(row[7]),
        "research": json.loads(row[8]), "states": json.loads(row[9]),
        "theory": json.loads(row[10]), "numerical": json.loads(row[11]),
        "observables": json.loads(row[12]), "results": json.loads(row[13]),
        "figures": json.loads(row[14]), "equations": json.loads(row[15]),
        "limitations": json.loads(row[16]), "references": json.loads(row[17]),
        "meta": json.loads(row[20])
    }

@app.get("/stats")
async def stats():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM papers")
    count = cur.fetchone()[0]
    cur.execute("SELECT year, COUNT(*) FROM papers GROUP BY year ORDER BY year")
    years = cur.fetchall()
    conn.close()
    return {"total_papers": count, "by_year": dict(years)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)