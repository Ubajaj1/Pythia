# Kitaru experiment results

| Metric | recorded | baseline-replay | swap-gpt4omini |
|---|---|---|---|
| coherence_rate | 0.980 ± 0.063 | 1.000 ± 0.000 | 1.000 ± 0.000 |
| parse_failure_rate | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 |
| target_validity_rate | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 |
| stance_volatility | 0.042 ± 0.018 | 0.046 ± 0.036 | 0.026 ± 0.010 |
| final_aggregate | 0.586 ± 0.153 | 0.548 ± 0.114 | 0.523 ± 0.108 |

## Direction agreement with the recording

- baseline-replay: 30%
- swap-gpt4omini: 20%

Sessions per arm: recorded=10, baseline-replay=10, swap-gpt4omini=10

## Paired view (each replay vs its own recording)

| Arm | Mean \|Δ final aggregate\| | SD | Max |
|---|---|---|---|
| baseline-replay (noise floor) | 0.108 | 0.057 | 0.199 |
| swap-gpt4omini | 0.205 | 0.121 | 0.336 |

Welch t ≈ 2.3 (p ≈ 0.04, n = 10 per arm): the swap moves outcomes about twice as far as re-running unchanged. Suggestive at this sample size, not conclusive.

Swap arm verified in Kitaru: all 10 result sessions have exactly 40 tick nodes served by `gpt-4o-mini` (requested `gpt-4.1-nano`) and no other node changed.

Unexplained: 6/10 replays in each arm ended in the neutral band (0.4–0.6) versus 1/10 recordings. Worth a follow-up; not attributed to Kitaru.

Setup: 5 README prompts × 2 = 10 recorded sessions; OpenAI `gpt-4.1-mini` (analysis, generation, judge) and `gpt-4.1-nano` (agent turns); 5 agents × 8 ticks, 50 LLM calls per session; 20 native replays via a local worker, 4 concurrent, ~32 s each.
