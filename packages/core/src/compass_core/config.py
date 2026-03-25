"""Loads .env variables natively."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KUZU_DB_PATH = os.getenv("KUZU_DB_PATH", ".compass/graph.kuzu")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
REPO_ROOT = Path(os.getenv("REPO_ROOT", "."))
