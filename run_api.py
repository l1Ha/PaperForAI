#!/usr/bin/env python3
"""Minimal run script: start FastAPI RAG server for Quantum Collision literature."""

import subprocess
import sys
import os
import time
from pathlib import Path

FASTAPI_CMD = [sys.executable, "-m", "uvicorn", "rag_api:app", "--host", "0.0.0.0", "--port", "8000"]

def main():
    print("⚛️  Starting Quantum Collision RAG API...")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠  OPENAI_API_KEY not set! Set it before running.")
        print("   export OPENAI_API_KEY='nvapi-...'")
    
    print("🚀 Starting FastAPI server...")
    proc = subprocess.Popen(
        FASTAPI_CMD,
        cwd=str(Path(__file__).parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for startup
    time.sleep(5)
    
    if proc.poll() is None:
        print("✓ FastAPI running at http://localhost:8000")
        print("   Test: curl -X POST http://localhost:8000/search -H 'Content-Type: application/json' -d '{\"query\":\"Penning ionization Rb\"}'")
    else:
        stdout = proc.stdout.read().decode(errors="replace")
        stderr = proc.stderr.read().decode(errors="replace")
        print("✗ FastAPI failed to start:")
        print(f"  stdout: {stdout[-300:]}")
        print(f"  stderr: {stderr[-300:]}")

if __name__ == "__main__":
    main()