"""Portkey / model configuration and the run-wide spend limits.

Loads .env from the project folder and every folder above it (nearest wins),
so the class-wide .env a few levels up works without copying the key around.

gpt-6-luna needs the Responses API for function tools (chat/completions rejects
tools + reasoning_effort on this model).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
for folder in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

# Every agent on the team runs the same model. Course budget assumes luna.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

# --- token / spend guard rails -------------------------------------------
# These bound a single run. They exist because the team is fully connected:
# any agent can ask any other agent, so without a ceiling a disagreement
# between two specialists can ping-pong until the budget is gone.
MAX_DELEGATIONS = int(os.getenv("MAX_DELEGATIONS", "10"))  # per run, all agents
MAX_DEPTH = int(os.getenv("MAX_DEPTH", "2"))  # boss → specialist → specialist
# 8 was too tight: a full ticket investigation (read tools, then a delegation,
# then a write) blew the limit mid-run and aborted the loop. 14 clears a real
# ticket with headroom while still capping a runaway agent.
MAX_REQUESTS_PER_AGENT = int(os.getenv("MAX_REQUESTS_PER_AGENT", "14"))  # model calls in one loop
# A five-agent run over three tickets measured ~78 MCP calls, so 60 starved the
# last agent to report. 140 leaves headroom without letting a loop run away.
MAX_TOOL_CALLS_PER_RUN = int(os.getenv("MAX_TOOL_CALLS_PER_RUN", "140"))  # MCP calls per run


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing. Put it in a .env in this project or a parent folder."
        )
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    client = AsyncOpenAI(
        api_key=require_api_key(),
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
