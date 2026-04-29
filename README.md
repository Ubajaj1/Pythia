# Pythia

### *Consult the oracle before you decide.*

> A multi-agent simulation engine that shows you how stakeholders respond to your decision — before you make it.

![license](https://img.shields.io/badge/license-Apache%202.0-blue)
![python](https://img.shields.io/badge/python-3.11+-blue)
![react](https://img.shields.io/badge/react-19-61dafb)

---

## What it does

You describe a decision in plain English. Pythia generates a cast of agents — investors, customers, critics, regulators — each with a persona, a cognitive bias, and relationships to the others. They argue tick by tick, shift stances, and try to reach consensus. You watch it happen in real time.

Agents whose reasoning doesn't match their actions get pulled into a self-correction loop. Their behavioral rules are rewritten and they re-enter the simulation. By run 5, the oracle is measurably more coherent than run 1.

---

## Quick start

**With an API key (recommended):**

```bash
git clone https://github.com/Ubajaj1/Pythia.git
cd Pythia
cp .env.example .env
# add ANTHROPIC_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY
docker compose up --build
```

Open `http://localhost` in your browser.

**With Ollama (local, no API key):**

```bash
docker compose --profile ollama up --build
docker compose exec ollama ollama pull llama3.1:8b
```

---

## Try it

Paste any of these into the prompt field:

| Scenario | Prompt |
|---|---|
| AI adoption | `Should our startup adopt AI coding tools for all engineering tasks?` |
| Fundraising | `Should we raise a Series A or stay bootstrapped?` |
| Policy | `Should a city ban single-use plastics in restaurants?` |
| Work model | `Should tech companies mandate a return to office 5 days a week?` |
| Platform governance | `Should a social media platform ban political advertising entirely?` |

Hit **Consult the Oracle** for a single run, or **Oracle Loop ↻** to run up to 5 iterations with self-correction.

---

## How it works

**1. Analyze** — one LLM call turns your prompt into a typed blueprint: scenario type, stance spectrum, archetypes, tick count.

**2. Generate** — agents are spawned in parallel: personas, cognitive biases (confirmation, loss aversion, anchoring, availability, status-quo, framing), initial stances, influence relationships.

**3. Simulate** — every tick, each agent reads its memory, its neighbors' last messages, and the aggregate stance, then emits `{stance, action, emotion, reasoning, message}`. Bias mechanics tug the stance. All agents update in parallel, so order doesn't bias the outcome.

**4. Evaluate** — after a run, each agent is scored for coherence: does the stated reasoning explain the action?

**5. Amend** — incoherent agents get additional behavioral rules. They re-enter the next run carrying what they learned. Coherence is plotted across runs.

Ensemble mode runs several parallel simulations and reports the distribution of outcomes — agreement across runs is signal, disagreement is genuine uncertainty. Backtest mode runs the same pipeline against a known outcome and scores the prediction on direction, aggregate error, and confidence match.

---

## Running without Docker

**Backend:**

```bash
pip install -e .
python -m pythia serve                       # API at http://localhost:8000
python -m pythia "Should we pivot to B2C?"   # one-shot CLI
python -m pythia oracle "Should we raise?"   # oracle loop
```

**Frontend:**

```bash
cd src/ui
npm install
npm run dev                                  # UI at http://localhost:5173
```

Set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY` in your shell, or run Ollama locally.

---

## Tech stack

| Layer | Stack |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn, httpx |
| Simulation | Custom opinion-dynamics engine, tick-based, parallel per-agent LLM calls |
| LLM providers | Anthropic, OpenAI, Groq, Ollama (auto-detected from env, token-bucket rate limited) |
| Frontend | React 19, Vite, Server-Sent Events for live streaming |
| Serving | Nginx (Docker) |

---

## Project layout

```
Pythia/
├── src/
│   ├── pythia/        backend: engine, oracle loop, API, LLM clients
│   └── ui/            frontend: React SPA
├── tests/             Python + JS tests
├── data/              run outputs and logs (gitignored)
├── docs/              architecture + design notes
└── docker-compose.yml full stack
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Named after the Oracle of Delphi — the most consulted seer in the ancient world.*
