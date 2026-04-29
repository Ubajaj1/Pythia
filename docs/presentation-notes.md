# Pythia — Speaker Notes

> Total budget: **6 minutes** for the page + live demo together.
> Target pacing: ~30s for hero, ~30s Who, ~45s What, ~45s Why, **~2m Demo**,
> ~1m Architecture, ~30s Decisions, ~30s Limitations + close.
>
> Read these cue cards top to bottom — each line is one beat. Short, declarative, confident.

---

## Hero — 15 to 30 seconds

- "This is Pythia — the line under it is the whole pitch: *consult the oracle before you decide.*"
- "It's a multi-agent simulation that shows you how stakeholders react to a decision — before you commit to it."

---

## Section 1 · Who am I? — 20 to 30 seconds

- "Hi, I'm Utkarsh. I build systems that behave like organisms — agents, feedback loops, interfaces you can watch work."
- "Pythia is solo full-stack. Backend, frontend, and the weird middle where LLMs meet opinion dynamics."
- "The reason I built it is on the next slide."

---

## Section 2 · What is Pythia? — 40 to 50 seconds

- "You type a decision in plain English — no form, no schema, no dropdowns."
- "Pythia spins up 5 to 8 agents. Each one has a persona, one cognitive bias from a curated catalog, and relationships to the others — who they respect, distrust, follow, rival."
- "Then the simulation ticks forward. Every tick, every agent reasons in parallel: what do I now think, how do I feel, what do I say, who am I saying it to?"
- "After the run, a coherence evaluator asks: did this agent's reasoning actually explain what they did? If not, they go to the Temple of Learning. Their rules get rewritten. They re-enter smarter."
- **Stats line, pointing at the tiles:** "16 biases, 4 LLM providers, 100+ tests, 5 oracle iterations max."

---

## Section 3 · Why Pythia? — 40 to 50 seconds

- "A single LLM gives you one confident-sounding answer. That's the problem."
- "A panel of 6 biased agents arguing gives you the *texture* of the decision — where consensus forms, who holds out, what would flip the room, where the hidden risk is."
- **Point at the two columns:** "Left column is what one LLM does. Right column is what we do differently — many voices, declared biases, influence graph driving disagreement, ensemble quantifying uncertainty."
- "Now let me show you."

---

## Section 4 · Demo — 2 minutes (the core of the talk)

> Click "Open the Oracle" or switch windows.

### Setup beat (15s)
- "Type the prompt. Let's use: *Should a city ban single-use plastics in restaurants?*"
- "I'll hit Consult the Oracle."

### What to narrate while it streams (45s)
- "Six agents just spawned — a restaurant owner, an environmental advocate, a health official, a council member, a resident, an industry lobbyist. Each one has a cognitive bias; you can see them in the sidebar."
- "Watch the stances move tick by tick. The graph on the left is the stance trajectory per agent. The thickness of the lines between agents — that's the influence graph. When someone sends a message, it lights up."
- "Notice the aggregate line climbing — that's the panel drifting toward consensus. But see those two lines that stay apart? That's the dissent. That's the value."

### Click through the verdict (30s)
- "The verdict report — one line of plain English plus confidence. Then arguments for, arguments against, the single biggest risk, and what could change to flip the decision."
- "These aren't generic. They cite *which agent* said what, because the engine tracked it."

### Click the method / influence / agent detail (30s)
- "Method report — how the oracle arrived at this verdict. The computed confidence is deterministic from stance spread, not a vibe from the LLM."
- "Click an agent — here's their full tick history. Persona, bias, behavioral rules, tick-by-tick reasoning, and the exact moment they shifted their stance."

### Oracle Loop beat (10s — optional if you're running long)
- "If I hit Oracle Loop, it runs again. Evaluator catches incoherent agents. Temple rewrites their rules. Run 5 is measurably more coherent than run 1."

> Come back to the page. Scroll to Architecture.

---

## Section 5 · Architecture — 60 to 75 seconds

> Point at the diagram while you talk. Don't read the boxes — read the *arrows*.

- "Five layers. Solid arrows are data flow. The dashed red path is the self-correction loop."
- "Prompt goes into the Analyzer — one LLM call turns English into a typed blueprint: scenario type, stance spectrum, archetypes, tick count."
- "Generator spawns agents in parallel — each archetype becomes an agent with persona, bias, rules, and an influence edge to its neighbors."
- "The Engine runs the tick loop. Every tick, every agent fires a parallel LLM call. They all read last tick's world — not each other's current thinking — so there's no turn-order bias. The UI streams these ticks live over Server-Sent Events."
- "After the run, the Evaluator asks per agent: was the reasoning coherent? If no, the Temple amends the rules. The amended agents re-enter the next run."
- "Everything sits on top of an LLMClient protocol — Anthropic, OpenAI, Groq, or Ollama, swapped by environment variable."

### If you have time, flag these from the numbered list below the diagram:
- **"Structure enforcement"** — "Every tick returns strict JSON. Pydantic validates. Parse fails fall back to a neutral tick instead of crashing the run."
- **"Emotion as feedback"** — "Emotion isn't decoration. It's stamped into memory and bleeds into the next tick. Anxious agents stay anxious. Confident ones double down. This is how herding emerges naturally."
- **"Bias in two layers"** — "The LLM gets text cues — framing, availability, authority. Then a mechanical function *nudges* the proposed stance — anchoring pulls toward initial, bandwagon toward aggregate, loss aversion asymmetric. Dialogue *and* trajectory both reflect the bias."
- **"Memory compression"** — "At 20 ticks we don't dump the full history. We keep the anchor tick, any pivot bigger than 0.10, and the last 3 ticks. Honest history without bloating context."
- **"Coherence, not accuracy"** — "We don't have ground truth for 'what will people think.' So we measure the strongest honest thing — did the reasoning explain the action?"
- **"Temple of Learning"** — "Amendments are additive by default. At 8-rule cap, Temple edits existing rules instead of just piling on. It also tunes bias_strength up or down."
- **"Ensemble for variability"** — "Same agents, fresh tick loops. Three runs agreeing is signal. Three runs disagreeing is genuine uncertainty — and we report it as *low* confidence. This is the honest answer to 'how sure are you?'"

---

## Section 6 · Design decisions — 30 to 45 seconds

> Don't read the whole table. Pick 3 that match what the audience cares about.

### If the audience is engineers, emphasize:
- "Parallel tick calls — cuts latency N× and eliminates turn-order bias."
- "LLMClient protocol — structural typing, any object with `generate(prompt) → dict` plugs in."
- "SSE end-to-end — ticks render as they stream, no blocking one-shots."

### If the audience is product / founders, emphasize:
- "Ensemble for variability — we don't pretend one run is the answer."
- "Backtest for calibration — against known outcomes, we score direction and error."
- "Two-layer bias — dialogue and dynamics both reflect the bias."

---

## Section 7 · Limitations — 30 to 45 seconds

> Pick **two** cards. Don't read all six. Pair it with what's next.

- **Rate limits:** "Free-tier Groq hit 40+ back-to-back 429s during a 6-agent run. Retry-with-backoff works, but stretches 30s to 90s. Next: adaptive concurrency per provider tier."
- **Coherence ≠ correctness:** "A run can be 100% coherent and still wrong. That's why backtesting is wired in — with a known outcome, we score direction and error. Next: grow the corpus."
- **Small-N panel:** "Six agents is a boardroom, not a market. Next: crowd particles driven by aggregate dynamics, with named agents riding on top."

---

## Section 8 · Connect / close — 15 to 20 seconds

- "One meme for the road — because predictions are hard, especially about the future."
- "Left QR is my LinkedIn — I'd love to talk if any of this landed for you."
- "Right QR is the repo — it's public, Apache 2.0, and the README walks you through running it locally in two minutes."
- "Thanks."

---

## Safety net — if you run over time

Drop these first, in this order:
1. Skip Oracle Loop demo beat — jump straight to the verdict.
2. Skip Design decisions section entirely — the architecture diagram already covered the key ones.
3. Collapse Limitations to one card (rate limits).
4. Skip the meme — go straight to QR codes.

## Safety net — if you run under time

Add these, in this order:
1. Run Oracle Loop live and point at the coherence-curve improvement.
2. Expand on emotion feedback: "Watch this anxious agent — on tick 5 they went from cautious anxiety to determined frustration. That's not scripted; that's the memory loop."
3. Walk through one agent's tick history in AgentDetail.
4. Ensemble demo — "Three runs. Two agree on support. One flips to low confidence. That's us being honest about uncertainty."

---

## One-liner closers for Q&A

- **"Why not just use a single LLM?"** → "One LLM is one voice. Pythia is a panel. The disagreement is the value."
- **"How do you know it's right?"** → "We measure two things: coherence within a run, and calibration against known outcomes when ground truth exists. We don't pretend one run is the truth — that's why ensemble mode exists."
- **"Can it scale to 1000 agents?"** → "Not today. Six-to-eight named agents is where it shines. The roadmap is crowd particles for the mass, named agents for the characters."
- **"Why not GPT-4 for everything?"** → "Cost. Haiku and Llama 3.1 8B are 10× cheaper and handle tick-level reasoning well. The LLMClient protocol means you can route per-archetype — cheap for reactive, precise for analytical."
- **"What's next?"** → "God's Eye View — injecting new variables mid-simulation. And a tick-triggered influence graph that rewires under stress."
