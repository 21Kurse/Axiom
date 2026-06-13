"""
NVIDIA Ising Calibration Client
Connects to the LiteLLM API proxy to invoke
the ising-calibration model for quantum waveform analysis.
Errors propagate to the caller — no silent fallbacks.
"""

import json
import re
import asyncio
import os
import urllib.request
import urllib.error
import logging
from typing import Dict, Any, Tuple

log = logging.getLogger("axiom-q.nvidia")

def _resolve_litellm_url() -> str:
    """Resolve the OpenAI-compatible /v1/chat/completions endpoint for LiteLLM."""
    explicit_url = os.getenv("LITELLM_URL")
    if explicit_url:
        return explicit_url.rstrip("/")

    base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
    if base_url.endswith("/v1/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"

# LiteLLM proxy configuration
LITELLM_URL = _resolve_litellm_url()
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY", "freecc")
MODEL_ID = os.getenv("LITELLM_MODEL", os.getenv("OPENAI_MODEL", "ising-calibration"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("LITELLM_REQUEST_TIMEOUT_SECONDS", "60"))


async def call_nvidia_ising_model(qubit_id: str, probabilities: list, noise_inputs: dict) -> dict:
    """
    Main async entry point. Sends telemetry data to the NVIDIA Ising
    calibration model via LiteLLM and returns parsed correction JSON.
    Raises on failure — caller must handle the exception.
    """
    prompt = _build_calibration_prompt(qubit_id, probabilities, noise_inputs)

    loop = asyncio.get_running_loop()
    raw_response = await loop.run_in_executor(None, _call_litellm_sync, prompt)
    result = _parse_model_response(raw_response)
    log.info("NVIDIA Ising model returned: %s", result)
    return result


def _build_calibration_prompt(qubit_id: str, probabilities: list, noise_inputs: dict) -> str:
    """Builds the text prompt sent to the NVIDIA Ising model."""
    probs_str = ", ".join(f"{p:.3f}" for p in probabilities)

    return (
        "You are a quantum hardware calibration engine. "
        "Analyze the following noisy Rabi oscillation probability data from a superconducting qubit "
        "and compute the calibration corrections needed to restore a clean Rabi oscillation.\n\n"
        f"Qubit: {qubit_id}\n"
        f"Noise inputs: t1_relaxation={noise_inputs.get('t1_relaxation', 0.0)}, "
        f"phase_damping={noise_inputs.get('phase_damping', 0.0)}\n"
        f"Raw P(|1>) telemetry across {len(probabilities)} Rabi drive steps:\n"
        f"[{probs_str}]\n\n"
        "Based on the decay envelope and phase drift visible in this data, "
        "compute the exact calibration corrections.\n\n"
        "Return ONLY a JSON object with these exact keys, no other text:\n"
        '{"drift_corrected_mhz": <float>, "pi_pulse_amp_mod": <float>, "confidence": <float>}'
    )


def _extract_correction_json(text: str) -> dict:
    """Extract the correction JSON object from model output text."""
    if not text:
        raise ValueError("Model returned empty text; no correction JSON found.")

    match = re.search(r'\{[^{}]*"drift_corrected_mhz"[^{}]*\}', text, re.DOTALL)
    if not match:
        match = re.search(r'\{.*?\}', text, re.DOTALL)

    if not match:
        raise ValueError(f"No JSON found in model output. text={text[:400]!r}")

    return json.loads(match.group(0))


def _parse_model_response(raw_response: str) -> dict:
    """Parse model response from LiteLLM (OpenAI-compatible format)."""
    response_text = raw_response.strip()
    if not response_text:
        raise ValueError("Empty response body from LiteLLM.")

    payload = json.loads(response_text)
    if not isinstance(payload, dict):
        raise ValueError("Unexpected response format from LiteLLM.")

    choices = payload.get("choices", [])
    if not choices:
        raise ValueError("No choices in LiteLLM response.")

    message = choices[0].get("message", {})
    if not message:
        raise ValueError("No message in LiteLLM response choices.")

    content = message.get("content", "")
    if not content:
        raise ValueError("Empty content from LiteLLM.")

    return _extract_correction_json(content)


def _call_litellm_sync(prompt: str) -> str:
    """Synchronous HTTP call to LiteLLM proxy."""
    body = json.dumps({
        "model": MODEL_ID,
        "max_tokens": 4096,
        "stream": False,
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        }]
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
        raise RuntimeError(f"LiteLLM connection refused at {LITELLM_URL}: {e.reason}") from e
