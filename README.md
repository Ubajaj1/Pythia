# Pythia
### *Consult the oracle before you decide.*

> A self-improving multi-agent simulation engine that shows you how the world responds to your decisions — before you make them.

---

## What is Pythia?

Most tools tell you *what* happened. Pythia tells you *what could happen* before you commit.

You describe a decision — a product launch, a pricing change, a content strategy, a market entry — and Pythia spins up thousands of agents representing market segments, audience archetypes, and system actors. They interact, react, and evolve. Agents that predict poorly are pulled into a **Temple of Learning** and self-correct using behavioral amendment loops. By run 5, the oracle is measurably smarter than run 1.

This is not a chatbot. This is a living, self-improving world that reacts to your decisions.

---

## How It Works

### 1. Input — feed it anything
- A document (article, report, policy draft)
- A live API feed (news, market data, Reddit, LinkedIn)
- A structured dataset (CSV, JSON)
- A plain English description of your decision

### 2. World Generation
- GraphRAG extracts entities and relationships
- Thousands of agents spawned with unique archetypes
- Each agent gets: biography, behavioral traits, social connections, memory

### 3. Simulation Runs
- Agents interact, form opinions, shift positions
- **God's Eye View** — inject new variables mid-simulation
- Watch the world reorganize in real time

### 4. The Oracle Loop (Self-Correction)
- After each run, agent predictions compared to ground truth
- Failing agents pulled into the **Temple of Learning**
- Behavioral rules rewritten via amendment loops
- Agents re-enter the simulation wiser
- Run 5 is measurably smarter than Run 1

### 5. Cross-Simulation Learning
- Insights from a finance simulation propagate to a market simulation
- A Research DAG tracks lineage of all learned insights

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Simulation engine | [OASIS by CAMEL-AI](https://github.com/camel-ai/oasis) |
| Agent memory | Zep Cloud |
| Knowledge graphs | GraphRAG |
| Skill self-improvement | Cognee |
| Cross-domain DAG | Hyperspace-inspired Research DAG |
| Visualization | React + D3 / Three.js |
| Deployment | Docker Compose |

---

## Use Cases

**Tier 1 — Demo-ready**
- Market sentiment: simulate retail vs institutional investor reactions to a financial event
- Content strategy: simulate audience response before publishing
- Product launch: simulate early adopter vs skeptic dynamics

**Tier 2 — Enterprise**
- Competitive intelligence: simulate competitor responses to strategic moves
- Policy stress-testing: simulate citizen segment reactions before rollout
- Supply chain resilience: simulate cascade failures

**Tier 3 — Moonshot**
- Crisis communications: simulate narrative evolution during a PR crisis
- Misinformation spread: find where to intervene
- Epidemic modeling: simulate population responses to health interventions

---

## Project Structure

```
Pythia/
├── src/
│   ├── agents/       ← Agent archetypes, personality seeding, memory
│   ├── simulation/   ← OASIS integration, world engine, God's Eye View
│   ├── skills/       ← Cognee integration, amendment loop, Temple logic
│   ├── ingestion/    ← Document, API, CSV, plain English input handlers
│   ├── feedback/     ← Ground truth comparison, accuracy tracking
│   └── ui/           ← React animated city, Temple building, split screen
├── data/
│   ├── raw/          ← Input feeds and documents
│   ├── processed/    ← Knowledge graphs and entity extractions
│   └── ground_truth/ ← Historical data for backtesting
├── demos/            ← Pre-built demo scenarios (finance, content, product)
├── docs/             ← Architecture diagrams, API docs
├── tests/
└── scripts/          ← Setup, Docker, utility scripts
```

---

## Roadmap

- [x] Project structure & planning
- [ ] Phase 1 — Document ingestion → GraphRAG → agent generation → basic OASIS simulation
- [ ] Phase 2 — Cognee oracle loop, ground truth comparison, Temple of Learning logic
- [ ] Phase 3 — Animated city UI, split screen demo, God's Eye View variable injection
- [ ] Phase 4 — Docker one-click setup, pre-built demos, public launch

---

## Contributing

Contributions are welcome. Please open an issue before submitting a large PR so we can align on direction.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Named after the Oracle of Delphi — the most consulted seer in the ancient world.*
