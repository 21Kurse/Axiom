"""
Standalone smoke test for the ising-calibration model via the LiteLLM proxy.

Mirrors the request structure used by backend.nvidia_client (system+user
messages + response_format=json_object), but with hardcoded sample telemetry
so it can run without a live WebSocket feed.
"""

import urllib.request
import json
import re
import os
from dotenv import load_dotenv
load_dotenv()  # read .env if present

# LiteLLM proxy configuration
LITELLM_URL = os.getenv("LITELLM_URL", "http://127.0.0.1:4000/v1/chat/completions")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", os.getenv("OPENAI_API_KEY", "freecc"))
MODEL_ID = os.getenv("LITELLM_MODEL", os.getenv("OPENAI_MODEL", "ising-calibration"))

# Sample Rabi oscillation telemetry (50 qutrit steps)
SAMPLE_PROBS = [
    0.02, 0.15, 0.38, 0.62, 0.81, 0.92, 0.97, 0.95, 0.85, 0.70,
    0.52, 0.33, 0.18, 0.08, 0.03, 0.05, 0.14, 0.30, 0.51, 0.69,
    0.82, 0.90, 0.93, 0.88, 0.77, 0.61, 0.43, 0.27, 0.14, 0.07,
    0.03, 0.06, 0.16, 0.33, 0.52, 0.70, 0.83, 0.91, 0.94, 0.89,
    0.78, 0.63, 0.45, 0.29, 0.15, 0.08, 0.04, 0.05, 0.13, 0.28,
]

messages = [
    {
        "role": "system",
        "content": (
            "You are a quantum hardware calibration engine. "
            "Given noisy Rabi oscillation telemetry and the injected noise parameters, "
            "compute the calibration corrections needed to restore a clean Rabi oscillation. "
            "You MUST respond with a single valid JSON object and nothing else "
            "(no prose, no markdown, no explanations, no code fences). "
            "Use exactly these three keys with float values: "
            "drift_corrected_mhz, pi_pulse_amp_mod, confidence."
        ),
    },
    {
        "role": "user",
        "content": (
            "Qubit: Q0\n"
            "Noise inputs: t1_relaxation=0.25, phase_damping=0.15\n"
            f"Raw P(|1>) telemetry across {len(SAMPLE_PROBS)} Rabi drive steps:\n"
            f"[{', '.join(f'{p:.3f}' for p in SAMPLE_PROBS)}]\n\n"
            "Output JSON now:"
        ),
    },
]

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
    resp = urllib.request.urlopen(req, timeout=120)
    raw = resp.read().decode("utf-8")
    payload = json.loads(raw)

    content = payload["choices"][0]["message"]["content"]
    print("=== MODEL TEXT OUTPUT ===")
    print(content)
    print()

    # Layered parser (mirrors backend.nvidia_client._extract_correction_json)
    parsed = None
    stripped = content.strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        if stripped.startswith("```"):
            first_newline = stripped.find("\n")
            if first_newline != -1:
                stripped = stripped[first_newline + 1 :]
            if stripped.endswith("```"):
                stripped = stripped[:-3]
        try:
            parsed = json.loads(stripped.strip())
        except json.JSONDecodeError:
            match = re.search(r'\{[^{}]*"drift_corrected_mhz"[^{}]*\}', content, re.DOTALL)
            if not match:
                match = re.search(r'\{.*?\}', content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))

    if parsed:
        print("=== PARSED JSON ===")
        print(json.dumps(parsed, indent=2))
    else:
        print("No JSON object found in output")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
