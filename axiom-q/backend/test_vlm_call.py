"""Test script - try the ising-calibration model via LiteLLM proxy."""
import urllib.request
import json
import re
import os

# LiteLLM proxy configuration (default: http://127.0.0.1:4000)
LITELLM_URL = os.getenv("LITELLM_URL", "http://127.0.0.1:4000/v1/chat/completions")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", os.getenv("OPENAI_API_KEY", "freecc"))
MODEL_ID = os.getenv("LITELLM_MODEL", os.getenv("OPENAI_MODEL", "ising-calibration"))

body = json.dumps({
    "model": MODEL_ID,
    "max_tokens": 4096,
    "stream": False,
    "messages": [
        {
            "role": "user",
            "content": (
                "You are a quantum hardware calibration engine. "
                "Analyze the following noisy Rabi oscillation probability data from a superconducting qubit.\n\n"
                "Qubit: Q0\n"
                "Noise inputs: t1_relaxation=0.25, phase_damping=0.15\n"
                "Raw P(|1>) telemetry across 50 Rabi drive steps:\n"
                "[0.02, 0.15, 0.38, 0.62, 0.81, 0.92, 0.97, 0.95, 0.85, 0.70, "
                "0.52, 0.33, 0.18, 0.08, 0.03, 0.05, 0.14, 0.30, 0.51, 0.69, "
                "0.82, 0.90, 0.93, 0.88, 0.77, 0.61, 0.43, 0.27, 0.14, 0.07, "
                "0.03, 0.06, 0.16, 0.33, 0.52, 0.70, 0.83, 0.91, 0.94, 0.89, "
                "0.78, 0.63, 0.45, 0.29, 0.15, 0.08, 0.04, 0.05, 0.13, 0.28]\n\n"
                "Based on the decay envelope and phase drift visible in this data, "
                "compute the calibration corrections needed to restore a clean Rabi oscillation.\n\n"
                "Return ONLY a JSON object with these exact keys, no other text:\n"
                '{"drift_corrected_mhz": <float>, "pi_pulse_amp_mod": <float>, "confidence": <float>}'
            )
        }
    ]
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
    data = json.loads(raw)

    content = data["choices"][0]["message"]["content"]
    print("=== MODEL TEXT OUTPUT ===")
    print(content)
    print()

    # Extract JSON from the model output
    match = re.search(r'\{[^{}]*"drift_corrected_mhz"[^{}]*\}', content, re.DOTALL)
    if not match:
        match = re.search(r'\{.*\}', content, re.DOTALL)

    if match:
        parsed = json.loads(match.group(0))
        print("=== PARSED JSON ===")
        print(json.dumps(parsed, indent=2))
    else:
        print("No JSON object found in output")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
