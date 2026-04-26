# Pythia
### *Consult the oracle before you decide.*

> A self-improving multi-agent simulation engine that shows you how the world responds to your decisions — before you make them.

---

## Quick Start (Docker)

**With an API key (recommended):**

```bash
git clone https://github.com/utkarshbajaj/pythia
cd pythia
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY or OPENAI_API_KEY
docker compose up --build
```

Open `http://localhost` in your browser.

**With Ollama (local, no API key):**

```bash
docker compose --profile ollama up --build
# First run pulls the model — takes a few minutes
docker compose exec ollama ollama pull llama3.1:8b
```

---

## What is Pythia?

You describe a decision. Pythia spins up a panel of agents representing different stakeholders — investors, customers, critics, advocates. They argue, shift positions, and reach (or fail to reach) consensus. Agents that reason poorly are pulled into a self-correction loop and re-enter the simulation smarter.

By run 5, the oracle is measurably more coherent than run 1.

---

## Try It Yourself

Paste any of these into the prompt field:

| Scenario | Prompt |
|----------|--------|
| AI adoption | `Should our startup adopt AI coding tools for all engineering tasks?` |
| Fundraising | `Should we raise a Series A or stay bootstrapped and grow profitably?` |
| Environment policy | `Should a city ban single-use plastics in restaurants?` |
| Remote work | `Should tech companies mandate a return to the office 5 days a week?` |
| Platform policy | `Should a social media platform ban political advertising entirely?` |

Hit **Consult the Oracle** for a single run, or **Oracle Loop ↻** to run 5 iterations with self-correction.

---

## How It Works

**1. Simulate** — Describe a decision. Pythia generates a cast of agents (archetypes, stances, roles) and runs a tick-by-tick opinion dynamics simulation. Each agent reacts to others, shifts position, and logs their reasoning.

**2. Analyze** — After each run, an evaluator scores coherence: do the final stances match the agents' stated reasoning? Incoherent agents are flagged.

**3. Oracle Loop** — Flagged agents are amended (behavioral rules rewritten). The simulation reruns. Repeat up to 5×. Coherence score plotted across runs.

---

## Running Without Docker

**Backend:**

```bash
pip install -e .
python -m pythia serve          # API at http://localhost:8000
# or: python -m pythia "Should we pivot to B2C?"
# or: python -m pythia oracle "Should we raise a Series A?"
```

**Frontend:**

```bash
cd src/ui
npm install
npm run dev                     # UI at http://localhost:5173
```

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in your shell, or run Ollama locally.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Agent simulation | Custom engine (opinion dynamics, tick-based) |
| Oracle loop | Self-correction evaluator + amendment loop |
| LLM providers | Anthropic, OpenAI, Ollama (auto-detected from env) |
| Frontend | React 19, Vite |
| Serving | Nginx (Docker) |

---

## Project Structure

```
Pythia/
├── src/
│   ├── pythia/        ← Backend: engine, oracle loop, API, LLM clients
│   └── ui/            ← Frontend: React SPA
├── tests/             ← 79 Python + 23 UI tests
├── data/              ← Simulation run outputs (gitignored)
├── docs/              ← Architecture diagram
├── Dockerfile         ← Backend image
├── docker-compose.yml ← Full stack (backend + nginx + optional Ollama)
└── .env.example       ← API key template
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Named after the Oracle of Delphi — the most consulted seer in the ancient world.*
