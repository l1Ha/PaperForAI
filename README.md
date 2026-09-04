# PaperForAI: 量子碰撞 / Penning 电离文献 RAG 系统

> 从 PDF 到结构化 JSON → 向量数据库 → 语义检索的完整闭环

## 🎯 核心流程

```
PDF (13 篇代表性论文)
    ↓ PyMuPDF 解析
Markdown + 文本
    ↓ NVIDIA Nemotron-3-Ultra (LLM)
结构化 JSON (Schema v1.0)
    ↓ Validator (公式/图表/参数/幻觉检查)
SQLite (开发) / PostgreSQL + pgvector (生产)
    ↓ FastAPI + 混合检索 (FTS5 + 向量)
RAG API 服务
```

## 📁 项目结构

```
PaperForAI/
├── schema_v1.json          # 物理化学文献 Schema v1.0
├── extractor.py            # PDF → LLM → JSON
├── validator.py            # 自动校验 (公式/图表/参数/幻觉)
├── db_sqlite.py            # SQLite 落库 + 混合检索
├── db_setup.sql            # PostgreSQL + pgvector 生产建表
├── ingest.py               # PostgreSQL 入库脚本
├── rag_api.py              # FastAPI RAG 服务
├── papers.db               # SQLite 数据库 (13 篇论文)
└── *.json                  # 抽取结果 (本地, 不上传)
```

## 🚀 快速开始

### 1. 环境准备
```bash
# LLM API (NVIDIA Nemotron)
export OPENAI_API_KEY="nvapi-xxx"
export OPENAI_BASE_URL="https://integrate.api.nvidia.com/v1"

# Python 依赖
pip install openai fitz json-repair fastapi uvicorn sentence-transformers
```

### 2. 单篇论文抽取 + 校验
```bash
python extractor.py "paper.pdf" "nvidia/nemotron-3-ultra-550b-a55b"
python validator.py "paper.json" "paper.pdf"
```

### 3. 批量处理 + 入库 (SQLite)
```bash
python db_sqlite.py *.json
```

### 4. 启动 RAG API 服务
```bash
uvicorn rag_api:app --reload --port 8000

# 测试
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Penning ionization rate coefficient cold molecular collisions", "top_k": 5}'
```

### 5. 生产部署 (PostgreSQL + pgvector)
```bash
# 1. 启动 pgvector
docker run -d --name pgvector -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=papers -p 5432:5432 pgvector/pgvector:pg16

# 2. 建表
psql -h localhost -U postgres -d papers -f db_setup.sql

# 3. 入库
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/papers"
python ingest.py *.json

# 4. 修改 rag_api.py 连接 PostgreSQL 即可
```

## 📊 Schema v1.0 关键字段

| 模块 | 核心字段 | 示例 |
|------|----------|------|
| **paper** | title, authors, journal, year, doi | "Simple Closed-Form Expression..." |
| **research** | field, system, reaction, research_question | He* + H₂ → He + H₂⁺ + e⁻ |
| **states** | initial_states, final_states, quantum_numbers | J, Ω, j, l, ε, parity |
| **theory** | method, hamiltonian, potential, basis, scattering_formalism | 非厄米绝热散射理论 |
| **numerical** | grid, partial_waves, convergence | sin-DVR, lmax=18, 1500 basis |
| **observables** | name, symbol, units, range | k(T), cm³/s, 1 mK–300 K |
| **results** | key_features, finding, agreement, figure_ref | "Good accord with Nat. Phys. 2017" |
| **figures** | id, caption, type, key_findings | Fig.1: rate coeff vs T |
| **equations** | id, latex, description | Eq.2: V_C(R,Θ) = Σ[V_k - iΓ_k/2]P_k |
| **references** | citation, context | Klein et al., Nat. Phys. 2017 (expt benchmark) |

## 🔍 搜索示例

```bash
# 自然语言查询
"Penning ionization rate coefficient cold molecular collisions"
"non-Hermitian adiabatic scattering theory"
"complex potential energy surface autoionization width Γ"
"He* H2 resonance sub-Kelvin"
"Fano-ADC method Penning ionization widths"
```

返回结构化结果：
```json
{
  "query": "...",
  "results": [{
    "id": "...",
    "title": "...",
    "year": 2018,
    "research_question": "...",
    "system": {...},
    "method": "Adiabatic variational theory + non-Hermitian scattering",
    "potential": {...},
    "observables": ["rate coefficient k(T)", ...],
    "key_results": ["Good accord with experiment...", "Anisotropy crucial..."],
    "figures": {"Fig.1": "Rate coeff vs T...", ...},
    "equations": {"Eq.2": "V_C(R,Θ) = Σ[V_k - iΓ_k/2]P_k(cosΘ)", ...}
  }]
}
```

## 📈 已收录论文 (13 篇)

| 年份 | 体系 | 方法 | 关键词 |
|------|------|------|--------|
| 2021 | Rydberg Rb/Rb* + Rb | Semiclassical | Tom & Jerry pairs |
| 2020 | Ne(³P₂) + N₂, CO | Merged beam expt | Stereodynamics |
| 2019 | Ne(³P₂) + N₂ | Merged beam expt | Sub-Kelvin |
| 2018 | He* + H₂ | Non-Hermitian adiabatic | Rate coeff, closed-form |
| 2018 | He* + H₂ | Fano-ADC-Stieltjes | Autoionization widths |
| 2017 | He* + H₂ | RVP (Padé) | Ab initio CPES |
| 2006 | He/Ne* + Ar | Cross sections | Rate constants |
| 2001 | CO + He(2³S) | 2D PIES | Electron spectroscopy |
| 1999 | He* + He* | Close-coupled | Magnetostatic trap |
| 1997 | Ne(3s,3p) + Ar | Ab initio widths | Γ(R) calculation |
| 1979 | He* + Ar | Multichannel | Discretized continuum |
| 1978 | He* + SO₂ | Flowing afterglow | SO⁺ fluorescence |
| 1976 | He(2³S) + Ar | Optical potential | Penning ionization |

## 🔧 生产环境迁移清单

- [ ] PostgreSQL 16 + pgvector 部署
- [ ] 运行 `db_setup.sql` 建表 + HNSW 索引
- [ ] 配置 `DATABASE_URL` 环境变量
- [ ] 运行 `ingest.py` 批量入库 (含 OpenAI embeddings)
- [ ] FastAPI 后端部署 (Docker/K8s)
- [ ] 前端界面 (可选: Streamlit/React)
- [ ] 监控 + 日志 + 限流

## 📝 版本历史

- **v1.0** (2026-09-05): 完整闭环 - Schema设计、13篇论文抽取、SQLite落库、FastAPI RAG服务、GitHub同步

## 📄 License

MIT License - 仅代码开源，PDF 文献不包含在仓库中 (版权原因)