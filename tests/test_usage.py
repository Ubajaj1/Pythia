"""Tests for per-run token and cost accounting."""

import asyncio

from pythia.usage import RunUsage, record_usage, start_usage, stop_usage


def test_no_scope_is_noop():
    record_usage("claude-haiku-4-5", 10, 10)


def test_records_tokens_and_cost():
    usage, token = start_usage()
    try:
        record_usage("claude-haiku-4-5", 1_000_000, 1_000_000)
        record_usage("claude-haiku-4-5", 0, 0)
    finally:
        stop_usage(token)
    assert usage.calls == 2
    assert usage.input_tokens == 1_000_000 and usage.output_tokens == 1_000_000
    assert abs(usage.cost_usd - 6.0) < 1e-9
    assert usage.by_model["claude-haiku-4-5"]["calls"] == 2


def test_unknown_model_makes_cost_unknown():
    usage, token = start_usage()
    try:
        record_usage("mystery-model", 10, 10)
    finally:
        stop_usage(token)
    assert usage.cost_usd is None


async def test_child_tasks_share_the_scope():
    usage, token = start_usage()
    try:
        async def call():
            record_usage("claude-haiku-4-5", 1, 1)
        await asyncio.gather(call(), call(), call())
    finally:
        stop_usage(token)
    assert usage.calls == 3


def test_to_dict_rounds_cost():
    u = RunUsage(calls=1, input_tokens=5, output_tokens=5, cost_usd=0.123456789)
    assert u.to_dict()["cost_usd"] == 0.123457
