"""Tests for the InfluenceGraph data structure."""

import pytest
from pythia.models import InfluenceGraph, InfluenceNode, InfluenceEdge


class TestInfluenceGraph:
    def test_starts_empty(self):
        g = InfluenceGraph()
        assert g.nodes == []
        assert g.edges == []

    def test_add_tick_state(self):
        g = InfluenceGraph()
        g.add_tick_state("a1", 1, 0.5, "hold", "waiting", "calm")
        assert len(g.nodes) == 1
        assert g.nodes[0].agent_id == "a1"
        assert g.nodes[0].tick == 1
        assert g.nodes[0].stance == 0.5

    def test_add_influence(self):
        g = InfluenceGraph()
        g.add_influence("a1", "a2", 3, "Buy now!", 0.7, 0.3, 0.45)
        assert len(g.edges) == 1
        edge = g.edges[0]
        assert edge.source_id == "a1"
        assert edge.target_id == "a2"
        assert edge.influence_delta == 0.15  # 0.45 - 0.3

    def test_get_agent_trajectory(self):
        g = InfluenceGraph()
        g.add_tick_state("a1", 1, 0.3, "sell", "fear", "anxious")
        g.add_tick_state("a2", 1, 0.7, "hold", "steady", "calm")
        g.add_tick_state("a1", 2, 0.25, "sell more", "panic", "terrified")

        traj = g.get_agent_trajectory("a1")
        assert len(traj) == 2
        assert traj[0].tick == 1
        assert traj[1].tick == 2

    def test_get_influences_on(self):
        g = InfluenceGraph()
        g.add_influence("a1", "a2", 1, "msg1", 0.5, 0.3, 0.35)
        g.add_influence("a3", "a2", 2, "msg2", 0.6, 0.35, 0.4)
        g.add_influence("a1", "a3", 1, "msg3", 0.5, 0.6, 0.55)

        influences = g.get_influences_on("a2")
        assert len(influences) == 2

    def test_get_influences_by(self):
        g = InfluenceGraph()
        g.add_influence("a1", "a2", 1, "msg1", 0.5, 0.3, 0.35)
        g.add_influence("a1", "a3", 2, "msg2", 0.5, 0.6, 0.55)
        g.add_influence("a2", "a1", 1, "msg3", 0.3, 0.5, 0.48)

        influences = g.get_influences_by("a1")
        assert len(influences) == 2

    def test_get_strongest_influence_chains(self):
        g = InfluenceGraph()
        g.add_influence("a1", "a2", 1, "small", 0.5, 0.5, 0.52)   # delta 0.02
        g.add_influence("a1", "a2", 2, "big", 0.5, 0.52, 0.8)     # delta 0.28
        g.add_influence("a3", "a2", 3, "medium", 0.6, 0.8, 0.65)  # delta -0.15

        top = g.get_strongest_influence_chains(top_n=2)
        assert len(top) == 2
        assert abs(top[0].influence_delta) >= abs(top[1].influence_delta)
        assert abs(top[0].influence_delta) == 0.28

    def test_get_herd_moments(self):
        g = InfluenceGraph()
        # Tick 1: all 3 agents shift positive — herd moment
        g.add_tick_state("a1", 1, 0.5, "hold", "ok", "calm")
        g.add_tick_state("a2", 1, 0.6, "buy", "ok", "calm")
        g.add_tick_state("a3", 1, 0.55, "buy", "ok", "calm")
        # Tick 2: all shift positive again
        g.add_tick_state("a1", 2, 0.6, "buy", "ok", "excited")
        g.add_tick_state("a2", 2, 0.7, "buy more", "ok", "excited")
        g.add_tick_state("a3", 2, 0.65, "buy", "ok", "excited")
        # Tick 3: mixed — not herd
        g.add_tick_state("a1", 3, 0.55, "sell", "ok", "worried")
        g.add_tick_state("a2", 3, 0.75, "buy", "ok", "excited")
        g.add_tick_state("a3", 3, 0.65, "hold", "ok", "neutral")

        herd = g.get_herd_moments(3, threshold=0.6)
        assert 2 in herd  # tick 2 should be herd (all positive)
        assert 3 not in herd  # tick 3 is mixed

    def test_get_herd_moments_empty_graph(self):
        g = InfluenceGraph()
        assert g.get_herd_moments(5) == []

    def test_influence_delta_calculated_correctly(self):
        g = InfluenceGraph()
        g.add_influence("a1", "a2", 1, "msg", 0.5, 0.3, 0.1)
        assert g.edges[0].influence_delta == -0.2  # 0.1 - 0.3

    def test_serialization_roundtrip(self):
        g = InfluenceGraph()
        g.add_tick_state("a1", 1, 0.5, "hold", "ok", "calm")
        g.add_influence("a1", "a2", 1, "msg", 0.5, 0.3, 0.35)

        data = g.model_dump()
        g2 = InfluenceGraph.model_validate(data)
        assert len(g2.nodes) == 1
        assert len(g2.edges) == 1
        assert g2.edges[0].influence_delta == 0.05
