"""Tests for the bias catalog and fuzzy resolver."""

import re
import pytest
from pythia.biases import (
    BIAS_CATALOG,
    BiasCatalogEntry,
    resolve_bias,
    get_bias_entry,
    format_bias_for_prompt,
)


class TestCatalogValidity:
    """Every catalog entry must have all required fields, unique IDs, and snake_case."""

    def test_catalog_is_not_empty(self):
        assert len(BIAS_CATALOG) >= 12, "Catalog should have at least 12 biases"

    def test_all_ids_are_unique(self):
        ids = list(BIAS_CATALOG.keys())
        assert len(ids) == len(set(ids))

    def test_all_ids_are_snake_case(self):
        for cid in BIAS_CATALOG:
            assert re.match(r"^[a-z][a-z0-9_]*$", cid), f"{cid} is not snake_case"

    def test_all_entries_have_required_fields(self):
        for cid, entry in BIAS_CATALOG.items():
            assert isinstance(entry, BiasCatalogEntry), f"{cid} is not a BiasCatalogEntry"
            assert entry.canonical_id == cid, f"Key {cid} != entry.canonical_id {entry.canonical_id}"
            assert entry.name, f"{cid} missing name"
            assert entry.scientific, f"{cid} missing scientific"
            assert entry.layman, f"{cid} missing layman"
            assert len(entry.behavioral_cues) >= 2, f"{cid} needs at least 2 behavioral cues"

    def test_behavioral_cues_are_strings(self):
        for cid, entry in BIAS_CATALOG.items():
            for cue in entry.behavioral_cues:
                assert isinstance(cue, str) and len(cue) > 5, f"{cid} has invalid cue: {cue!r}"


class TestResolveBias:
    """Fuzzy-match resolver: known variants map to canonical IDs."""

    def test_exact_canonical_id(self):
        assert resolve_bias("loss_aversion") == "loss_aversion"

    def test_human_readable_name(self):
        assert resolve_bias("Loss Aversion") == "loss_aversion"

    def test_hyphenated_variant(self):
        assert resolve_bias("loss-aversion") == "loss_aversion"

    def test_fear_of_losing(self):
        assert resolve_bias("fear of losing") == "loss_aversion"

    def test_anchoring_bias_variant(self):
        assert resolve_bias("Anchoring Bias") == "anchoring"

    def test_fomo_maps_to_optimism(self):
        assert resolve_bias("FOMO Drive") == "optimism_bias"

    def test_status_quo(self):
        assert resolve_bias("status quo bias") == "status_quo_bias"

    def test_bandwagon(self):
        assert resolve_bias("bandwagon") == "bandwagon_effect"

    def test_social_proof(self):
        assert resolve_bias("Social Proof") == "bandwagon_effect"

    def test_sunk_cost(self):
        assert resolve_bias("sunk cost") == "sunk_cost_fallacy"

    def test_dunning_kruger_variants(self):
        assert resolve_bias("Dunning-Kruger") == "dunning_kruger"
        assert resolve_bias("dunning kruger effect") == "dunning_kruger"

    def test_empty_string_falls_back(self):
        result = resolve_bias("")
        assert result in BIAS_CATALOG

    def test_unknown_string_falls_back(self):
        result = resolve_bias("completely_made_up_bias_xyz")
        assert result in BIAS_CATALOG

    def test_all_canonical_ids_resolve_to_themselves(self):
        for cid in BIAS_CATALOG:
            assert resolve_bias(cid) == cid


class TestGetBiasEntry:
    def test_valid_id(self):
        entry = get_bias_entry("anchoring")
        assert entry.name == "Anchoring Bias"

    def test_invalid_id_raises(self):
        with pytest.raises(KeyError):
            get_bias_entry("nonexistent_bias")


class TestFormatBiasForPrompt:
    def test_contains_name_and_definition(self):
        text = format_bias_for_prompt("loss_aversion")
        assert "Loss Aversion" in text
        assert "Kahneman" in text

    def test_contains_behavioral_cues(self):
        text = format_bias_for_prompt("anchoring")
        assert "initial data point" in text.lower() or "starting position" in text.lower()

    def test_unknown_id_returns_fallback_string(self):
        text = format_bias_for_prompt("nonexistent")
        assert "nonexistent" in text
