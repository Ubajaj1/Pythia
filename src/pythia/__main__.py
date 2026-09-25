"""CLI entry point: python -m pythia"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pythia.config import LOG_DIR, LOG_LEVEL, OLLAMA_BASE_URL, OLLAMA_MODEL, RUNS_DIR


def _print_summary(result) -> None:
    """Print a human-readable summary to stdout."""
    s = result.scenario
    print(f"\n{'═' * 3} PYTHIA — {s.title} {'═' * 3}\n")
    print("Agents:")
    for agent in result.agents:
        final_stance = agent.initial_stance
        for tick in result.ticks:
            for event in tick.events:
                if event.agent_id == agent.id:
                    final_stance = event.stance
        direction = "▲" if final_stance > agent.initial_stance else "▼" if final_stance < agent.initial_stance else "─"
        print(f"  {agent.name:<22} [{agent.role}]  stance: {agent.initial_stance:.2f} → {final_stance:.2f}  {direction}")

    sm = result.summary
    first_agg = result.ticks[0].aggregate_stance if result.ticks else 0
    print(f"\nAggregate: {first_agg:.2f} → {sm.final_aggregate_stance:.2f}")
    print(f"Consensus: {'Yes' if sm.consensus_reached else 'No'}")
    bs = sm.biggest_shift
    delta = bs.to_stance - bs.from_stance
    print(f"Biggest shift: {bs.agent_id} ({delta:+.2f}) — {bs.reason}")
    print(f"\nFull run saved to data/runs/{result.run_id}.json")


async def _run(args: argparse.Namespace) -> None:
    from pythia.llm import build_role_clients
    from pythia.orchestrator import run_simulation

    llm, fast_llm = build_role_clients(provider=args.provider, ollama_url=args.ollama_url, model=args.model)
    try:
        result = await run_simulation(
            prompt=args.prompt,
            context=args.context,
            llm=llm,
            fast_llm=fast_llm,
            runs_dir=args.runs_dir,
        )
        _print_summary(result)
    finally:
        await llm.close()
        if fast_llm is not None:
            await fast_llm.close()


async def _run_oracle(args: argparse.Namespace) -> None:
    from pythia.llm import build_role_clients
    from pythia.oracle_loop import run_oracle_loop

    llm, fast_llm = build_role_clients(provider=args.provider, ollama_url=args.ollama_url, model=args.model)
    try:
        oracle_result = await run_oracle_loop(
            prompt=args.prompt,
            context=args.context,
            max_runs=args.runs,
            llm=llm,
            fast_llm=fast_llm,
            runs_dir=args.runs_dir,
        )
        if not oracle_result.runs:
            print("Oracle loop returned no runs.")
            return
        print(f"\n{'═' * 3} PYTHIA ORACLE — {oracle_result.runs[0].result.scenario.title} {'═' * 3}")
        print(f"Ran {len(oracle_result.runs)} simulation(s)\n")
        for record in oracle_result.runs:
            score_pct = round(record.coherence_score * 100)
            amended = ", ".join(record.amended_agent_ids) or "none"
            print(f"  Run {record.run_number}: coherence {score_pct}%  |  amended: {amended}")
        print(f"\nFinal coherence: {round(oracle_result.coherence_history[-1] * 100)}%")
    finally:
        await llm.close()
        if fast_llm is not None:
            await fast_llm.close()


def _serve(args: argparse.Namespace) -> None:
    import uvicorn
    from pythia.api import create_app

    app = create_app(provider=args.provider, ollama_url=args.ollama_url, model=args.model)
    uvicorn.run(app, host="0.0.0.0", port=args.port)


SUBCOMMANDS = ("serve", "oracle")


def _add_global_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ollama-url", default=OLLAMA_BASE_URL, help="Ollama API base URL")
    parser.add_argument("--model", default=None, help="Model name (overrides provider default)")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["ollama", "openai", "anthropic", "groq"],
        help="LLM provider (default: auto-detect from env vars)",
    )
    parser.add_argument("--runs-dir", default=RUNS_DIR, help="Output directory for run JSON files")
    parser.add_argument(
        "--log-level",
        default=LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log level (file always gets DEBUG)",
    )
    parser.add_argument("--log-dir", default=LOG_DIR, help="Directory for log files")


def _command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pythia", description="Pythia simulation engine",
        epilog='Run a single simulation with: pythia [options] "<decision or question>"',
    )
    _add_global_options(parser)
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Server port")

    oracle_parser = subparsers.add_parser("oracle", help="Run oracle loop (multi-run self-improving simulation)")
    oracle_parser.add_argument("prompt", help="Decision or question to simulate")
    oracle_parser.add_argument("--runs", type=int, default=5, help="Maximum number of simulation runs")
    oracle_parser.add_argument("--context", default=None, help="Additional context paragraph")
    return parser


def _run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pythia", description="Run one Pythia simulation")
    _add_global_options(parser)
    parser.add_argument("prompt", help="Decision or question to simulate")
    parser.add_argument("--context", default=None, help="Additional context paragraph")
    parser.set_defaults(command=None)
    return parser


def _first_positional(argv: list[str]) -> str | None:
    """The first argument that isn't an option or an option's value (every global option takes one)."""
    skip = False
    for arg in argv:
        if skip:
            skip = False
        elif arg in ("-h", "--help"):
            continue
        elif arg.startswith("-"):
            skip = "=" not in arg
        else:
            return arg
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    """`pythia serve`, `pythia oracle "<prompt>"`, or `pythia "<prompt>"` for a single run.

    One parser can't take both subcommands and a bare prompt (argparse reads the prompt as
    a subcommand name), so the first positional argument picks the parser.
    """
    first = _first_positional(argv)
    if first is None or first in SUBCOMMANDS:
        args = _command_parser().parse_args(argv)
        if args.command is None:
            args.prompt = None
        return args
    return _run_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    from pythia.logger import setup_logging
    setup_logging(level=args.log_level, log_dir=args.log_dir)

    if args.command == "serve":
        _serve(args)
    elif args.command == "oracle":
        asyncio.run(_run_oracle(args))
    elif args.prompt:
        asyncio.run(_run(args))
    else:
        _command_parser().print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
