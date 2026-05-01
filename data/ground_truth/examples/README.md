# Ground Truth Examples

This folder contains reference backtest cases that ship with the repository. Use these to validate Pythia's calibration or as templates for your own cases.

Files in the parent `data/ground_truth/` folder are gitignored — put private or experimental cases there. Files in this `examples/` folder are tracked by git and shared across laptops.

## Case file format

Each case is a JSON file matching the `BacktestCase` schema (see `src/pythia/models.py`):

```json
{
  "case_id": "unique-slug",
  "domain": "business_strategy | earnings | policy | ...",
  "description": "one-sentence summary",
  "prompt": "the decision question posed to Pythia",
  "context": "optional context paragraph",
  "document_path": "optional path to a companion .txt document",
  "ground_truth_outcome": {
    "aggregate_stance": 0.72,
    "confidence": "low | moderate | high",
    "notes": "free-form explanation of what actually happened"
  }
}
```

### Optional `aggregate_stance_rationale` block

Ground-truth aggregate stance is inherently a judgment call. To keep that reasoning auditable, cases may include an `aggregate_stance_rationale` block documenting:

- **summary** — one-line intuition for the chosen value
- **methodology** — how signals were weighted
- **signals** — list of evidence that pulled the value up or down
- **alternative_framings** — other defensible values and when to use them
- **direction_threshold** — minimum threshold for "direction correct" scoring

This block is ignored at load time (Pydantic `extra='ignore'`) — it exists purely for documentation and reproducibility.

## How to run one

In the UI:
1. Click the **⏱ Backtest** button to enable backtest mode
2. Paste the case's `prompt` into the input
3. Upload the `document_path` file (if present)
4. Enter the `aggregate_stance` and `confidence` values from the JSON
5. Click **Run Backtest**

From the CLI:
```bash
# Runs all cases in data/ground_truth/*.json (top level only — not examples/)
# To batch-run examples, copy them into the parent folder first:
cp data/ground_truth/examples/*.json data/ground_truth/
python -m pythia backtest
```

## Included cases

| File | Domain | Decision | Ground truth |
|---|---|---|---|
| `netflix-password-sharing.json` | Business strategy | Should Netflix proceed with password crackdown May 2023? | 0.72 (high confidence) — decision succeeded |
| `example-fed-rate-hike.json` | Earnings | How will markets react to Fed 50bps hike? | 0.35 (moderate) — mildly bearish |

## Adding a new example

1. Create `your-case.json` here following the schema
2. Optionally add a companion `your-case.txt` with source material for grounding
3. Include the `aggregate_stance_rationale` block if the value required judgment
4. Commit both files — they'll ship to anyone pulling the repo
