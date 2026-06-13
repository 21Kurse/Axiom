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


CORRECTION_KEYS = ("drift_corrected_mhz", "pi_pulse_amp_mod", "confidence")


def _build_messages(qubit_id: str, probabilities: list, noise_inputs: dict) -> list[dict]:
    """
    Build a structured messages list for the chat completion call.
    Splitting system + user lets the model separate the calibration task spec
    from the telemetry data, which improves JSON purity.
    """
    probs_str = ", ".join(f"{p:.3f}" for p in probabilities)

    system = (
        "You are a quantum hardware calibration engine. "
        "Given noisy Rabi oscillation telemetry and the injected noise parameters, "
        "compute the calibration corrections needed to restore a clean Rabi oscillation. "
        "IMPORTANT: T1 relaxation and T2 dephasing are PHYSICAL ENVIRONMENT parameters "
        "that cannot be changed by calibration. Instead, calibration adjusts the microwave "
        "control pulse parameters: drift_corrected_mhz compensates hardware frequency drift, "
        "and pi_pulse_amp_mod scales the pulse amplitude to counteract amplitude errors. "
        "You MUST respond with a single valid JSON object and nothing else "
        "(no prose, no markdown, no explanations, no code fences). "
        "Use exactly these three keys with float values: "
        f"{', '.join(CORRECTION_KEYS)}."
    )

    user = (
        f"Qubit: {qubit_id}\n"
        f"Noise inputs: t1_relaxation={noise_inputs.get('t1_relaxation', 0.0)}, "
        f"phase_damping={noise_inputs.get('phase_damping', 0.0)}\n"
        f"Raw P(|1>) telemetry across {len(probabilities)} Rabi drive steps:\n"
        f"[{probs_str}]\n\n"
        "Output JSON now:"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _strip_code_fence(text: str) -> str:
    """Strip ```json ... ``` fences the model sometimes wraps output in anyway."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def _extract_by_keywords(text: str) -> dict:
    """
    Last-resort fallback: regex-extract the three correction values from prose
    like 'drift_corrected_mhz: 0.02' or 'pi_pulse_amp_mod = 1.15'.
    """
    out: dict = {}
    for key in CORRECTION_KEYS:
        match = re.search(rf'{re.escape(key)}\s*[:=]\s*(-?\d+(?:\.\d+)?)', text)
        if match:
            out[key] = float(match.group(1))
    return out


def _extract_correction_json(text: str) -> dict:
    """
    Layered JSON extractor:
      1) Direct parse — works when response_format=json_object is honored.
      2) Strip ```json fences and retry — catches the model ignoring the format.
      3) Strict regex `{...}` — catches JSON embedded in surrounding prose.
      4) Relaxed regex `\\{.*?\\}` — catches truncated/single-line output.
      5) Keyword regex — worst case, the model answered in prose but at least
         gave us the numbers.
    Raises a descriptive ValueError if every layer fails.
    """
    if not text:
        raise ValueError("Model returned empty text; no correction JSON found.")

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

    # Layer 3: strict regex (no nested braces)
    match = re.search(r'\{[^{}]*"drift_corrected_mhz"[^{}]*\}', text, re.DOTALL)
    if not match:
        match = re.search(r"\{[^{}]*\"pi_pulse_amp_mod\"[^{}]*\}", text, re.DOTALL)

    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Layer 4: relaxed first { ... } pair
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Layer 5: keyword extraction from prose
    keyword_result = _extract_by_keywords(text)
    if keyword_result:
        log.warning(
            "Model returned prose-only output; extracted corrections via keyword regex: %s",
            keyword_result,
        )
        # Fill any missing keys with 0.0 so the downstream contract is satisfied
        for key in CORRECTION_KEYS:
            keyword_result.setdefault(key, 0.0)
        return keyword_result

    raise ValueError(f"No JSON found in model output. text={text[:400]!r}")


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


def _call_litellm_sync(messages: list[dict]) -> str:
    """
    Synchronous HTTP call to LiteLLM proxy.

    Uses OpenAI-compatible `response_format={"type": "json_object"}` to coerce
    the model into emitting pure JSON. This is a strongly-typed hint that
    LiteLLM passes through to providers like NVIDIA NIM that support it.
    """
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
        raise RuntimeError(f"LiteLLM connection refused at {LITELLM_URL}: {e.reason}") from e


async def call_nvidia_ising_model(qubit_id: str, probabilities: list, noise_inputs: dict, image_base64: str = None) -> dict:
    """
    Main async entry point. Sends telemetry data (and image) to the local VLM proxy
    and returns parsed correction JSON.
    Raises on failure — caller must handle the exception.
    """
    probs_str = ", ".join(f"{p:.3f}" for p in probabilities)
    text_content = (
        f"Qubit: {qubit_id}\n"
        f"Noise inputs: t1_relaxation={noise_inputs.get('t1_relaxation', 0.0)}, "
        f"phase_damping={noise_inputs.get('phase_damping', 0.0)}\n"
        f"Raw P(|1>) telemetry across {len(probabilities)} Rabi drive steps:\n"
        f"[{probs_str}]\n\n"
        "Output JSON now:"
    )
    
    # Send both text and image if available
    user_message_content = [{"type": "text", "text": text_content}]
    if image_base64:
        user_message_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })
    
    messages = [
        {"role": "system", "content": "You are a quantum hardware calibration engine. Respond ONLY with a valid JSON object. Keys: drift_corrected_mhz, pi_pulse_amp_mod, confidence."},
        {"role": "user", "content": user_message_content}
    ]

    loop = asyncio.get_running_loop()
    raw_response = await loop.run_in_executor(None, _call_litellm_sync, messages)
    
    # Process the proxy's response using the robust regex layers
    result = _parse_model_response(raw_response)
    log.info("NVIDIA Ising model returned: %s", result)
    return result
