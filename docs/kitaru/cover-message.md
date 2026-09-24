Hi [name],

As promised, here's feedback on Kitaru from wiring it into Pythia, my multi-agent decision simulator: no framework, no tool calls, three model roles per run. I recorded 10 sessions and ran 20 native replays: an unchanged noise-floor arm, and one swapping only the agent-turn model via a model-map override.

Top three:
1. The model-map override is excellent. It swapped exactly the 40 agent-turn calls per session, even across providers, and replays ran unattended in about 30 s each.
2. Built-in evaluators fail on uv < 0.9 (`--exclude-newer-package kitaru=0 days`); the preflight misses it, and since evaluators are mandatory, every replay fails before the agent runs.
3. Custom, non-framework agents need a short code example. I learned the API from the SDK source.

Full memo with results and a ranked friction list: [memo link]

Happy to walk through it.
Utkarsh
