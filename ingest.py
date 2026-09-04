#!/usr/bin/env python3
"""
Ingest extracted JSON into PostgreSQL + pgvector.
Generates embedding for the paper content.
"""
import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import Json
from openai import OpenAI


def get_embedding(text: str, model: str = "text-embedding-3-small") -> list:
    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.getenv("OPENAI_API_KEY")
    )
    resp = client.embeddings.create(model=model, input=text[:8000])
    return resp.data[0].embedding


def build_full_text(paper: dict) -> str:
    """Concatenate searchable text from paper."""
    parts = []
    if paper.get("paper", {}).get("title"):
        parts.append(paper["paper"]["title"])
    if paper.get("research", {}).get("research_question"):
        parts.append(paper["research"]["research_question"])
    if paper.get("theory", {}).get("method"):
        parts.append(paper["theory"]["method"])
    # Add observable names
    for obs in paper.get("observables", []):
        if obs.get("name"):
            parts.append(obs["name"])
    # Add result key features
    for res in paper.get("results", []):
        for k in ["key_features", "finding", "agreement"]:
            if res.get(k):
                parts.append(str(res[k]))
    return " ".join(parts)


def ingest(json_path: str, dsn: str = None):
    with open(json_path) as f:
        paper = json.load(f)

    # Generate embedding
    print("Generating embedding...")
    full_text = build_full_text(paper)
    embedding = get_embedding(full_text)

    # Connect to DB
    dsn = dsn or os.getenv("DATABASE_URL", "postgresql://localhost:5432/papers")
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # Insert
    paper_id = str(uuid.uuid4())
    p = paper.get("paper", {})
    r = paper.get("research", {})
    s = paper.get("states", {})
    t = paper.get("theory", {})
    n = paper.get("numerical", {})
    
    cur.execute("""
        INSERT INTO papers (
            id, source_pdf, title, authors, journal, year, doi, keywords,
            research, states, theory, numerical, observables, results,
            figures, equations, limitations, references,
            embedding, full_text, meta
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        paper_id,
        paper.get("metadata", {}).get("source_pdf", Path(json_path).stem + ".pdf"),
        p.get("title"),
        Json(p.get("authors", [])),
        p.get("journal"),
        p.get("year"),
        p.get("doi"),
        p.get("keywords", []),
        Json(r), Json(s), Json(t), Json(n),
        Json(paper.get("observables", [])),
        Json(paper.get("results", [])),
        Json(paper.get("figures", [])),
        Json(paper.get("equations", [])),
        Json(paper.get("limitations", [])),
        Json(paper.get("references", [])),
        embedding,
        full_text,
        Json(paper.get("metadata", {}))
    ))

    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ Ingested paper {paper_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <extracted.json>")
        sys.exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY")
        sys.exit(1)
    
    ingest(sys.argv[1])