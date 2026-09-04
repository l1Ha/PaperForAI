#!/usr/bin/env python3
"""
Validator for extracted physics paper JSON.
Checks: formulas, figures, references, physics params, units, hallucinations.
"""
import json
import re
import fitz
from pathlib import Path
from typing import Dict, List, Any, Tuple


def load_pdf_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)


def check_formulas(extracted: dict, pdf_text: str) -> Dict[str, Any]:
    """Verify equation LaTeX appears in paper."""
    issues = []
    equations = extracted.get("equations", [])
    for eq in equations:
        latex = eq.get("latex", "")
        if latex and latex not in pdf_text:
            # Try to find similar
            key_parts = [p for p in re.split(r'[\s=+\-*/^_(){}]', latex) if len(p) > 3]
            found = any(part in pdf_text for part in key_parts)
            if not found:
                issues.append(f"Equation '{eq.get('id', '?')}': LaTeX not found in PDF")
    return {"passed": len(issues) == 0, "issues": issues, "checked": len(equations)}


def check_figures(extracted: dict, pdf_text: str) -> Dict[str, Any]:
    """Verify figure captions and references."""
    issues = []
    figures = extracted.get("figures", [])
    for fig in figures:
        caption = fig.get("caption", "")
        fig_id = fig.get("id", "")
        if caption and caption[:50] not in pdf_text:
            issues.append(f"Figure {fig_id}: caption not found in PDF")
        if fig_id and fig_id not in pdf_text:
            issues.append(f"Figure {fig_id}: ID not referenced in PDF text")
    return {"passed": len(issues) == 0, "issues": issues, "checked": len(figures)}


def check_references(extracted: dict, pdf_text: str) -> Dict[str, Any]:
    """Verify reference citations exist."""
    issues = []
    refs = extracted.get("references", [])
    for ref in refs:
        citation = ref.get("citation", "")
        if citation:
            # Check if first author + year appears
            author_year = re.search(r'(\w+)\s+et\s+al\.\s+(\d{4})', citation)
            if author_year:
                author, year = author_year.groups()
                if f"{author}.*{year}" not in pdf_text and f"{author} {year}" not in pdf_text:
                    issues.append(f"Reference not found in PDF: {citation[:80]}")
    return {"passed": len(issues) == 0, "issues": issues, "checked": len(refs)}


def check_physics_params(extracted: dict, pdf_text: str) -> Dict[str, Any]:
    """Check for hallucinated physics parameters."""
    issues = []
    warnings = []
    
    # Check theory.potential terms
    pot = extracted.get("theory", {}).get("potential", {})
    terms = pot.get("terms", {})
    for term, desc in terms.items():
        if term not in pdf_text and term.lower() not in pdf_text.lower():
            warnings.append(f"Potential term '{term}' not explicitly in PDF (may be inferred)")
    
    # Check quantum numbers
    qnums = extracted.get("states", {}).get("quantum_numbers", [])
    for qn in qnums:
        if qn not in pdf_text:
            warnings.append(f"Quantum number '{qn}' not found in PDF")
    
    # Check observables symbols
    for obs in extracted.get("observables", []):
        sym = obs.get("symbol", "")
        if sym and sym not in pdf_text:
            warnings.append(f"Observable symbol '{sym}' not in PDF")
    
    return {"passed": len(issues) == 0, "issues": issues, "warnings": warnings}


def check_units(extracted: dict) -> Dict[str, Any]:
    """Basic unit consistency checks."""
    issues = []
    unit_pattern = re.compile(r'(cm\^3|s\^-1|K|mK|eV|meV|a\.?u\.?|a₀|bohr|hartree)')
    
    for obs in extracted.get("observables", []):
        units = obs.get("units", "")
        if units and not unit_pattern.search(units):
            issues.append(f"Observable '{obs.get('name')}': unusual units '{units}'")
    
    return {"passed": len(issues) == 0, "issues": issues}


def check_hallucination(extracted: dict, pdf_text: str) -> Dict[str, Any]:
    """Heuristic: check specific claims appear in text."""
    issues = []
    
    # Check key results have textual support
    for res in extracted.get("results", []):
        finding = str(res.get("key_features", "")) + str(res.get("finding", ""))
        # At least some keywords should appear
        keywords = [w for w in finding.split() if len(w) > 4]
        matches = sum(1 for k in keywords if k.lower() in pdf_text.lower())
        if keywords and matches < max(1, len(keywords) * 0.3):
            issues.append(f"Result claim poorly supported by text: {finding[:100]}")
    
    return {"passed": len(issues) == 0, "issues": issues}


def validate_all(extracted: dict, pdf_path: str) -> dict:
    pdf_text = load_pdf_text(pdf_path)
    
    checks = {
        "formulas": check_formulas(extracted, pdf_text),
        "figures": check_figures(extracted, pdf_text),
        "references": check_references(extracted, pdf_text),
        "physics_params": check_physics_params(extracted, pdf_text),
        "units": check_units(extracted),
        "hallucination": check_hallucination(extracted, pdf_text)
    }
    
    all_passed = all(c["passed"] for c in checks.values())
    total_issues = sum(len(c.get("issues", [])) for c in checks.values())
    total_warnings = sum(len(c.get("warnings", [])) for c in checks.values())
    
    return {
        "overall_passed": all_passed,
        "total_issues": total_issues,
        "total_warnings": total_warnings,
        "checks": checks
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python validator.py <extracted.json> <source.pdf>")
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        extracted = json.load(f)
    
    report = validate_all(extracted, sys.argv[2])
    
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    if not report["overall_passed"]:
        print(f"\n⚠ Validation FAILED: {report['total_issues']} issues, {report['total_warnings']} warnings")
        sys.exit(1)
    else:
        print(f"\n✓ Validation PASSED ({report['total_warnings']} warnings)")