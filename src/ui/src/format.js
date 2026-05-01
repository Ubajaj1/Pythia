// Shared presentation helpers. Keep this tiny — one concern per export.

// Map of canonical backend bias IDs → human-readable display names. Mirrors
// the `name` field in src/pythia/biases.py so the UI reads the same label the
// Oracle's Method panel already shows (which comes from build_methodology).
const BIAS_DISPLAY_NAMES = {
  anchoring: 'Anchoring Bias',
  authority_bias: 'Authority Bias',
  availability_heuristic: 'Availability Heuristic',
  bandwagon_effect: 'Bandwagon Effect',
  confirmation_bias: 'Confirmation Bias',
  dunning_kruger: 'Dunning-Kruger Effect',
  framing_effect: 'Framing Effect',
  in_group_bias: 'In-Group Bias',
  hindsight_bias: 'Hindsight Bias',
  loss_aversion: 'Loss Aversion',
  negativity_bias: 'Negativity Bias',
  optimism_bias: 'Optimism Bias',
  overconfidence: 'Overconfidence Bias',
  recency_bias: 'Recency Bias',
  status_quo_bias: 'Status Quo Bias',
  sunk_cost_fallacy: 'Sunk Cost Fallacy',
}

/**
 * Format a bias identifier for display.
 *
 * Handles three shapes gracefully:
 *   - canonical snake_case IDs from the backend (e.g. "availability_heuristic")
 *   - already-formatted names from the Oracle's Method panel (e.g. "Anchoring Bias")
 *   - legacy display strings from the demo/scenarios (e.g. "FOMO Drive")
 *
 * Falls back to Title-Casing the underscores out so unknown IDs still look clean.
 */
export function formatBias(bias) {
  if (!bias) return ''
  const str = String(bias).trim()
  if (!str) return ''

  // Already in the catalog — use the canonical display name
  if (BIAS_DISPLAY_NAMES[str]) return BIAS_DISPLAY_NAMES[str]

  // Catalog lookup with normalized key (handles case/whitespace drift)
  const normalized = str.toLowerCase().replace(/[^a-z0-9]/g, '_')
  if (BIAS_DISPLAY_NAMES[normalized]) return BIAS_DISPLAY_NAMES[normalized]

  // Unknown value — if it looks like snake_case, title-case it. Otherwise
  // leave it alone (it's probably already a human-readable string).
  if (str.includes('_')) {
    return str
      .split('_')
      .filter(Boolean)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }
  return str
}
