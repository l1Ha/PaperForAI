#!/usr/bin/env python3
"""
PDF -> Structured JSON extractor for quantum collision / Penning ionization papers.
Uses LLM with strict JSON schema.
"""
import json
import json_repair
import os
import sys
from pathlib import Path
from datetime import datetime
from openai import OpenAI
import fitz

SCHEMA_PATH = Path(__file__).parent / "schema_v1.json"

with open(SCHEMA_PATH) as f:
    SCHEMA = json.load(f)

SYSTEM_PROMPT = """You are an expert in quantum molecular collision physics and Penning ionization literature.
Extract structured information from the paper content following the JSON schema exactly.

CRITICAL RULES:
1. NEVER hallucinate. If information is not in the text, use null, [], or {}.
2. Preserve original LaTeX for equations, symbols, quantum numbers.
3. Extract numerical values with units (e.g., "1 mK – 300 K", "cm³/s").
4. Link figures/tables/equations to their content.
5. Distinguish between: theory vs numerical vs experimental results.
6. For potentials: extract functional form, expansion terms, parameters.
7. For quantum numbers: use standard notation (J, Ω, j, l, ε, parity).
8. For observables: include symbol, units, temperature/energy range.
9. References: keep citation string and context (what it's cited for).
10. Output ONLY valid JSON matching the schema. No markdown, no commentary."""

USER_PROMPT_TEMPLATE = """Extract information from this paper into the JSON schema.

Schema (keys only, for reference):
{schema_keys}

Paper content (Markdown + extracted text):
{paper_content}

Return ONLY the JSON object matching the schema."""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract full text from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    texts = []
    for i, page in enumerate(doc):
        text = page.get_text()
        texts.append(f"--- PAGE {i+1} ---\n{text}")
    return "\n\n".join(texts)


def build_user_prompt(paper_content: str) -> str:
    schema_keys = json.dumps(list(SCHEMA.keys()), ensure_ascii=False, indent=2)
    return USER_PROMPT_TEMPLATE.format(
        schema_keys=schema_keys,
        paper_content=paper_content[:100000]  # truncate if too long
    )


def call_llm(prompt: str, model: str = "gpt-4o-mini") -> dict:
    """Call LLM with JSON mode."""
    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.getenv("OPENAI_API_KEY")
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=8000
    )
    return json_repair.loads(resp.choices[0].message.content)


def extract_paper(pdf_path: str, model: str = "gpt-4o-mini") -> dict:
    """Full extraction pipeline for one paper."""
    print(f"[1/3] Extracting text from {pdf_path}...")
    paper_text = extract_text_from_pdf(pdf_path)
    
    print(f"[2/3] Calling LLM ({model})...")
    prompt = build_user_prompt(paper_text)
    extracted = call_llm(prompt, model)
    
    print(f"[3/3] Post-processing...")
    extracted["metadata"] = {
        "parsed_by": f"PyMuPDF + {model}",
        "parsed_at": datetime.now().isoformat(),
        "schema_version": "1.0",
        "validation_status": "llm_extracted",
        "source_pdf": os.path.basename(pdf_path)
    }
    
    return extracted


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extractor.py <pdf_path> [model]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o-mini"
    
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    result = extract_paper(pdf_path, model)
    
    out_path = Path(pdf_path).with_suffix(".json")
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved to {out_path}")