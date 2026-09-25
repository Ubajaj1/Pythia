"""CLI argument parsing: plain runs, subcommands, and global options in any order."""

import pytest

from pythia.__main__ import parse_args


def test_plain_prompt_runs_a_simulation():
    args = parse_args(["Should we raise a Series A?"])
    assert args.command is None and args.prompt == "Should we raise a Series A?"


def test_global_options_and_context_before_the_prompt():
    args = parse_args(["--provider", "openai", "--context", "Seed stage", "Should we raise?"])
    assert args.provider == "openai" and args.context == "Seed stage" and args.prompt == "Should we raise?"


def test_option_with_equals_before_the_prompt():
    args = parse_args(["--log-level=DEBUG", "Should we raise?"])
    assert args.log_level == "DEBUG" and args.prompt == "Should we raise?"


def test_oracle_subcommand():
    args = parse_args(["--provider", "groq", "oracle", "Should we raise?", "--runs", "2", "--context", "c"])
    assert args.command == "oracle" and args.prompt == "Should we raise?" and args.runs == 2 and args.context == "c"


def test_serve_subcommand():
    args = parse_args(["serve", "--port", "9000"])
    assert args.command == "serve" and args.port == 9000


def test_no_arguments_has_no_prompt():
    args = parse_args([])
    assert args.command is None and args.prompt is None


def test_prompt_that_starts_like_a_word_is_still_a_prompt():
    assert parse_args(["oracles are cool?"]).prompt == "oracles are cool?"
