# Pythia — Speaker Notes

> Total budget: **6 minutes** for the page + live demo together.
> Target pacing: ~20s hero, ~20s Who, ~40s What, ~50s Why, **~2m Demo**, ~1m Architecture, ~30s Decisions, ~30s Limitations, ~10s close.
>
> The page is now deliberately sparse; each bullet is one line. The detail below is what you say out loud.

---

## Hero — 15 to 20 seconds

- "This is Pythia. The line under it is the whole pitch: consult the oracle before you decide."
- "It is a multi-agent simulation that shows you how stakeholders react to a decision, before you commit to it."

---

## Section 1 · Who am I? — 15 to 20 seconds

- "I'm Utkarsh. I build at Amazon."
- "I build for fun on the side too, and this is one of those builds."

---

## Section 2 · What is Pythia? — 35 to 45 seconds

> The box says: **Decision making. Play it out before making it.** Read the box, then elaborate.

- "Every meaningful decision has second-order effects you cannot talk your way through. Pythia lets you play them out before you commit."
- "You describe a decision in plain English. Pythia spawns a panel of agents, each with a persona, a cognitive bias, and relationships to the others. They argue tick by tick. You watch it happen."
- Walk the four bullets: **solo passion project**, **plain English in**, **agents with teeth**, **self-correcting**.
- "16 biases in a hand-curated catalog, four LLM providers, 100+ tests, and if a run goes sideways we iterate up to five times."

---

## Section 3 · Why Pythia? — 40 to 50 seconds

> Four bullets, read each, add the expansion.

1. **Why simulate at all.**
   > "Simulation is how engineers stress-test bridges, how epidemiologists model outbreaks, how pilots train for failure modes. You surface dynamics you would otherwise discover the expensive way, after committing."
2. **Why LLMs fit.**
   > "Authoring believable personas with consistent internal reasoning used to be the hard part. LLMs do that natively. Give one a persona, a bias, a memory, and a world state, and it reasons in character for hundreds of ticks."
3. **Why Pythia is robust.**
   > "An LLM improvising personas drifts. Pythia pins it down. Every bias comes from a canonical catalog with citations. Every stance passes through a mechanical correction function. Every run is evaluated for coherence. The LLM is the actor, the engine is the director."
4. **Why not just roleplay with one LLM.**
   > "Asking GPT-4 to simulate six stakeholders gives you one voice doing six impressions. In Pythia, each agent is its own prompt, its own memory, its own bias. They disagree because they actually have different contexts."

---

## Section 4 · Demo — 2 minutes (core of the talk)

> Switch to `http://localhost`.

### Setup (10 s)
- "Prompt: *Should a city ban single-use plastics in restaurants?* Hit Consult the Oracle."

### While it streams (45 s)
- "Six agents just spawned: a restaurant owner, an environmental advocate, a health official, a council member, a resident, and an industry lobbyist. Each has a cognitive bias — listed in the sidebar."
- "Watch the stance graph. Each line is one agent's position over time. The links that light up between them are the influence graph; when someone sends a message, the edge fires."
- "See the aggregate line climbing? That's consensus forming. But the two lines staying apart are the dissent. That's the value."

### Verdict report (30 s — image 1 on the slide)
- "This is the verdict report. One-line call, then arguments for, arguments against, the key risk, and what could flip the decision."
- "These aren't generic. They cite which agent said what, because the engine tracked it."

### Agent detail (30 s — image 2 on the slide)
- "Click an agent. Here's their full tick history: persona, bias, behavioural rules, tick-by-tick reasoning, and the exact moment they shifted their stance."
- "This is how you audit the panel. Every stance change has a paper trail."

### Oracle Loop (10 s, optional)
- "Hit Oracle Loop. It runs again. The evaluator catches incoherent agents, the Temple rewrites their rules, and the coherence curve climbs run over run."

> Come back to the page. Scroll to Architecture.

---

## Section 5 · Architecture — 60 to 75 seconds

> Point at the diagram. Don't read boxes, read arrows. Then walk the 9 mechanisms.

### Arrow-by-arrow (20s)
- "Prompt in → Analyzer — one LLM call to produce a typed blueprint."
- "Generator spawns agents in parallel — persona, bias, rules, influence edges."
- "Engine runs the tick loop. Every tick, every agent fires a parallel LLM call. They all read last tick's world, so there's no turn-order bias. UI streams over SSE."
- "After the run, Evaluator asks per agent: was this reasoning coherent? If not, Temple amends the rules. Amended agents re-enter the next run. Dashed red is that loop."
- "Underneath, LLMClient protocol — Anthropic, OpenAI, Groq, Ollama — swapped by env var."

### The nine mechanisms, expanded (read the one-liner, add this)

1. **Structure is non-negotiable.** "Every tick returns strict JSON — stance, action, emotion, reasoning, message, influence target. Pydantic validates. Parse failures substitute a neutral confused tick instead of crashing."

2. **Emotion is feedback.** "Emotion isn't decoration. Whatever an agent feels this tick gets stamped into memory and bleeds into the next tick's prompt. Anxious agents stay anxious. That's how herding and momentum emerge, same as in a room."

3. **Bias in two layers.** "LLM gets behavioural cues in the prompt — how a framing-effect person hears a proposal. Then a mechanical function nudges the proposed stance. Anchoring pulls toward initial, bandwagon toward aggregate, loss aversion is asymmetric. Dialogue and trajectory both reflect the bias."

4. **Guardrails keep runs stable.** "This was the biggest risk to solve. Stances clamped to 0.0 to 1.0. Bias coefficients capped so no single pull can swing more than 0.15 in a tick. Memory compressed to anchor plus pivots plus last three ticks. Rules cap at 8 per agent, after that Temple edits. Malformed influence targets fall back to null instead of hallucinated agents. Small mechanisms, but together they keep 20-tick runs stable."

5. **Parallel ticks.** "All agents reason simultaneously against last tick's world. Kills turn-order bias. Cuts wall-clock by N times."

6. **Coherence is the honest metric.** "We don't have ground truth for 'what will people think.' So we measure the strongest honest thing — did the stated reasoning explain the action? Flag only direct contradictions, self-contradictions within a tick, or large shifts with empty reasoning."

7. **Temple rewrites failures.** "Failing agents get 1 to 3 new rules. At 8-rule cap, Temple edits instead. Also recommends raising or lowering bias_strength. Amended agent re-enters the next run carrying the lesson."

8. **Ensemble quantifies uncertainty.** "One run is an anecdote. Three runs agreeing is signal. Three disagreeing is genuine uncertainty — and we report it as low confidence. That's what calibrated actually looks like."

9. **Backtest is the accuracy check.** "When history has a known outcome, we run blind and score direction with a 0.1 neutral band, aggregate error, and confidence match. Turns coherent into correct where that's possible."

---

## Section 6 · Design decisions — 30 seconds

> Don't read the whole list. Pick three that match the audience.

**For engineers:** parallel per-tick calls, LLMClient protocol, SSE end-to-end.
**For product:** ensemble for variability, backtest for calibration, two-layer bias.
**For researchers:** coherence over accuracy, hand-authored catalog, additive amendment.

---

## Section 7 · Limitations — 30 seconds

> Pick two cards. Don't read all six.

- "Rate limits: free-tier providers 429 under parallel ticks. Retry with backoff works, but a 30s run stretches to 90."
- "Coherence is not correctness. A run can be internally consistent and still wrong. Backtesting helps where history exists."
- "Six agents is a boardroom, not a market. The roadmap is crowd particles for the mass with named agents on top."

---

## Section 8 · Close — 10 to 15 seconds

- "Meme on the left: are you this guy? If so, we should talk."
- "Middle QR is my LinkedIn. Right QR is the repo — public, Apache 2.0."
- "Thanks."

---

## Safety nets

### Running over
1. Skip Oracle Loop demo beat.
2. Skip Design Decisions entirely (arch already covered them).
3. Collapse Limitations to one card.

### Running under
1. Run Oracle Loop live, point at the coherence curve.
2. Expand the emotion loop: "This anxious agent shifted from cautious anxiety to determined frustration on tick 5. That's memory loop, not scripting."
3. Walk one agent's tick history in detail.
4. Ensemble demo: "Three runs. Two agree. One flips. Reported as low confidence."
