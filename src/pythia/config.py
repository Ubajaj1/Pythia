"""Pythia configuration defaults."""

import os

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_TICK_COUNT = 20
RUNS_DIR = "data/runs"
LOG_DIR = "data/logs"
LOG_LEVEL = "INFO"

# Provider switching — set env vars to use OpenAI or Anthropic instead of Ollama
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
