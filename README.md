# PaperForAI
From raw text to AI-ready knowledge!

Translate physics-chemistry papers into structured data that AI can reliably understand and use.

## Schema-first roadmap (Quantum collision / Penning ionization)

> **Do not start with GROBID or vector DB first.**
> First design and validate a domain schema on a small familiar set of papers.

### Phase 1 (must do first): define v1 schema from 10–20 familiar papers

Start with about 10 representative papers (e.g., Penning ionization, quantum scattering, coupled-channel, time-dependent wavepacket, ultracold collision, molecular reaction dynamics), then refine this JSON:

```json
{
  "paper": {
    "title": "",
    "authors": [],
    "journal": "",
    "year": "",
    "doi": ""
  },
  "research": {
    "field": [],
    "system": {},
    "reaction": "",
    "research_question": ""
  },
  "states": {
    "initial_state": [],
    "final_state": [],
    "quantum_numbers": []
  },
  "theory": {
    "method": "",
    "Hamiltonian": [],
    "basis": "",
    "potential": "",
    "boundary_condition": ""
  },
  "numerical": {
    "grid": {},
    "time_step": "",
    "basis_size": "",
    "partial_waves": "",
    "convergence": ""
  },
  "observables": ["cross section", "DCS", "ICS"],
  "results": [],
  "figures": [],
  "equations": [],
  "limitations": [],
  "references": []
}
```

Then extend with domain-specific keys:

- Core physics symbols/entities: `H`, `V(R)`, `Γ(R)`, `S-matrix`, `J`, `Ω`, `Λ`, `Σ`, `ℓ`, `M`
- Structured parameters: `collision_energy`, `temperature`, `magnetic_field`, `initial_channel`, `final_channel`, `partial_wave`, `scattering_length`, `phase_shift`, `ICS`, `DCS`, `energy_distribution`, `angular_distribution`, `autoionization_width`, `optical_potential`

### Phase 2: run one real PDF end-to-end

```text
PDF
 ↓
MinerU / Docling
 ↓
Markdown + JSON
 ↓
LLM
 ↓
Physics-Chemistry JSON
 ↓
Manual verification
```

Manual verification checklist:

- Equations preserved (including subscripts/superscripts)
- Figure-caption alignment is correct
- Tables are not shifted or misparsed
- References are correctly linked
- Physical parameters are extracted, not hallucinated

### Phase 3: scale only after Phase 2 passes

Scale gradually: 100 → 1,000 → 10,000 papers.

## Immediate next action

Provide **one most representative PDF** first (for example your `Kr* + Rb` Penning ionization paper) to design the first production-ready schema and downstream pipeline:

`PDF → structured JSON → database → RAG`
