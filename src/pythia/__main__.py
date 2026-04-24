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
    from pythia.llm import build_llm_client
    from pythia.orchestrator import run_simulation

    llm = build_llm_client(provider=args.provider, ollama_url=args.ollama_url, model=args.model)
    try:
        result = await run_simulation(
            prompt=args.prompt,
            context=args.context,
            llm=llm,
            runs_dir=args.runs_dir,
        )
        _print_summary(result)
    finally:
        await llm.close()


async def _run_oracle(args: argparse.Namespace) -> None:
    from pythia.llm import build_llm_client
    from pythia.oracle_loop import run_oracle_loop

    llm = build_llm_client(provider=args.provider, ollama_url=args.ollama_url, model=args.model)
    try:
        oracle_result = await run_oracle_loop(
            prompt=args.prompt,
            context=args.context,
            max_runs=args.runs,
            llm=llm,
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


def _serve(args: argparse.Namespace) -> None:
    import uvicorn
    from pythia.api import create_app

    app = create_app(provider=args.provider, ollama_url=args.ollama_url, model=args.model)
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pythia", description="Pythia simulation engine")
    parser.add_argument("--ollama-url", default=OLLAMA_BASE_URL, help="Ollama API base URL")
    parser.add_argument("--model", default=None, help="Model name (overrides provider default)")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["ollama", "openai", "anthropic"],
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

    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Server port")

    oracle_parser = subparsers.add_parser("oracle", help="Run oracle loop (multi-run self-improving simulation)")
    oracle_parser.add_argument("prompt", help="Decision or question to simulate")
    oracle_parser.add_argument("--runs", type=int, default=5, help="Maximum number of simulation runs")
    oracle_parser.add_argument("--context", default=None, help="Additional context paragraph")

    parser.add_argument("prompt", nargs="?", default=None, help="Decision or question to simulate")
    parser.add_argument("--context", default=None, help="Additional context paragraph")

    args = parser.parse_args()

    from pythia.logger import setup_logging
    setup_logging(level=args.log_level, log_dir=args.log_dir)

    if args.command == "serve":
        _serve(args)
    elif args.command == "oracle":
        asyncio.run(_run_oracle(args))
    elif args.prompt:
        asyncio.run(_run(args))
    else:
        parser.print_help()
        sys.exit(1)


main()
