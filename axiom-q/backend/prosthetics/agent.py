"""
Prosthetics VLM Agent
======================
Sends the ``heatmap_noisy.png`` image to the NVIDIA Ising-Calibration-1-35B
vision API (via the existing LiteLLM proxy) for automated diagnosis of
pressure drift in the prosthetic socket grid.

The VLM receives a base64-encoded heatmap and a calibration-specific system
prompt.  Its JSON response is parsed into corrections that the healing phase
can apply.

Architecture
------------
Reuses the same LiteLLM proxy, URL resolution, API-key handling, and layered
JSON extraction logic from :pymod:`backend.nvidia_client` to stay consistent
with the Axiom.Q codebase.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("axiom-q.prosthetics.agent")

# ── LiteLLM / NVIDIA config (mirrors nvidia_client.py) ────────────────

def _resolve_litellm_url() -> str:
    explicit_url = os.getenv("LITELLM_URL")
    if explicit_url:
        return explicit_url.rstrip("/")
    base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
    if base_url.endswith("/v1/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


LITELLM_URL = _resolve_litellm_url()
LITELLM_API_KEY = (
    os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY", "freecc")
)
MODEL_ID = os.getenv(
    "LITELLM_MODEL", os.getenv("OPENAI_MODEL", "ising-calibration")
)
REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("LITELLM_REQUEST_TIMEOUT_SECONDS", "60")
)

# ── System prompt (user-specified) ─────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a prosthetic socket calibration agent. "
    "You are given a side-by-side pressure heatmap. "
    "Identify which cells in the drifted state are out of range compared "
    "to the target. Return ONLY a JSON object with: "
    "drift_zone (string), affected_cells (list of [row,col]), "
    "cell_corrections (dict mapping cell ID to target kPa), "
    "and confidence (float 0–1)"
)

# Expected top-level keys in the VLM response
EXPECTED_KEYS = ("drift_zone", "affected_cells", "cell_corrections", "confidence")


# ── Image encoding ─────────────────────────────────────────────────────

def _encode_image_base64(image_path: str) -> str:
    """Read an image file and return its base64-encoded string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Message builder ────────────────────────────────────────────────────

def _build_messages(
    image_b64: str,
    drift_cells: list[tuple[int, int]],
) -> list[dict]:
    """
    Build the OpenAI-compatible messages list with an image_url content part
    (base64 data URI) for the vision model.
    """
    drift_desc = ", ".join(f"[{r},{c}]" for r, c in drift_cells)

    user_content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{image_b64}",
            },
        },
        {
            "type": "text",
            "text": (
                f"The following cells were flagged as drifted by quantum telemetry: "
                f"{drift_desc}.\n\n"
                "Analyze the heatmap and return the calibration JSON now."
            ),
        },
    ]

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ── JSON extraction (layered, same strategy as nvidia_client.py) ───────

def _strip_code_fence(text: str) -> str:
    """Strip ```json ... ``` fences the model sometimes wraps output in."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def _extract_json(text: str) -> dict:
    """
    Layered JSON extractor tuned for the prosthetics VLM response.

    1) Direct parse
    2) Strip code fences and retry
    3) Regex for outermost { ... } block
    4) Keyword fallback for partial responses
    """
    if not text:
        raise ValueError("Model returned empty text; no JSON found.")

    stripped = text.strip()

    # Layer 1: direct parse
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Layer 2: strip code fences
    unfenced = _strip_code_fence(stripped)
    try:
        parsed = json.loads(unfenced)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Layer 3: regex for JSON object containing an expected key
    match = re.search(r'\{[^{}]*"drift_zone"[^{}]*\}', text, re.DOTALL)
    if not match:
        match = re.search(r'\{[^{}]*"affected_cells"[^{}]*\}', text, re.DOTALL)
    if not match:
        # Try to find the outermost { ... } pair (greedy)
        match = re.search(r'\{.*\}', text, re.DOTALL)

    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Layer 4: keyword extraction fallback
    result: dict[str, Any] = {}
    conf_match = re.search(r'confidence\s*[:=]\s*(\d+(?:\.\d+)?)', text)
    if conf_match:
        result["confidence"] = float(conf_match.group(1))
    zone_match = re.search(r'drift_zone\s*[:=]\s*["\']?([^"\'}\n,]+)', text)
    if zone_match:
        result["drift_zone"] = zone_match.group(1).strip()
    if result:
        log.warning("Extracted partial JSON via keyword regex: %s", result)
        result.setdefault("drift_zone", "unknown")
        result.setdefault("affected_cells", [])
        result.setdefault("cell_corrections", {})
        result.setdefault("confidence", 0.0)
        return result

    raise ValueError(f"No JSON found in model output. text={text[:400]!r}")


def _parse_model_response(raw_response: str) -> dict:
    """Parse the OpenAI-compatible chat completion response."""
    payload = json.loads(raw_response)
    choices = payload.get("choices", [])
    if not choices:
        raise ValueError("No choices in LiteLLM response.")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise ValueError("Empty content from LiteLLM.")
    return _extract_json(content)


# ── HTTP call (mirrors nvidia_client._call_litellm_sync) ──────────────

def _call_litellm_sync(messages: list[dict]) -> str:
    """Synchronous HTTP POST to the LiteLLM proxy."""
    body = json.dumps({
        "model": MODEL_ID,
        "max_tokens": 4096,
        "stream": False,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_API_KEY}"

    req = urllib.request.Request(LITELLM_URL, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LiteLLM HTTP {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"LiteLLM connection refused at {LITELLM_URL}: {e.reason}"
        ) from e


# ── Public API ─────────────────────────────────────────────────────────

async def analyze(
    heatmap_path: str,
    drift_cells: list[tuple[int, int]],
) -> dict[str, Any]:
    """
    Send the heatmap image to the NVIDIA Ising-Calibration-1-35B vision API
    via the LiteLLM proxy and return the parsed calibration diagnosis.

    Parameters
    ----------
    heatmap_path : str
        Absolute path to ``heatmap_noisy.png``.
    drift_cells : list[tuple[int, int]]
        (row, col) pairs where quantum telemetry detected drift.

    Returns
    -------
    dict
        Parsed VLM response with keys:
        ``drift_zone``, ``affected_cells``, ``cell_corrections``, ``confidence``.

    Raises
    ------
    RuntimeError
        If the LiteLLM proxy is unreachable or returns an HTTP error.
    ValueError
        If the model response cannot be parsed into valid JSON.
    """
    log.info("Encoding heatmap %s as base64 for VLM...", heatmap_path)
    image_b64 = _encode_image_base64(heatmap_path)
    log.info("Image encoded (%d bytes base64). Building messages...",
             len(image_b64))

    messages = _build_messages(image_b64, drift_cells)

    log.info("Calling LiteLLM at %s (model=%s)...", LITELLM_URL, MODEL_ID)
    loop = asyncio.get_running_loop()
    raw_response = await loop.run_in_executor(None, _call_litellm_sync, messages)

    result = _parse_model_response(raw_response)
    log.info("VLM diagnosis: %s", result)

    # Normalise into the healing-phase contract
    result.setdefault("drift_zone", "unknown")
    result.setdefault("affected_cells", [])
    result.setdefault("cell_corrections", {})
    result.setdefault("confidence", 0.0)

    return result
