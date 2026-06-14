# Axiom.Q — Autonomous Quantum Calibration Dashboard

Real-time quantum calibration dashboard with NVIDIA Ising-model-powered analysis via LiteLLM.

```
┌──────────────────┐      WebSocket       ┌─────────────────────────┐      HTTP      ┌────────────┐     HTTPS     ┌────────────┐
│  Vite + React UI │ ───────────────────► │  FastAPI (port 8081)    │ ────────────► │   LiteLLM  │ ────────────► │  NVIDIA    │
│  (port 5173)     │ ◄──── HTTP REST ──── │  + Qiskit Aer sim       │ ◄──────────── │ (port 4000)│ ◄──────────── │  NIM API   │
└──────────────────┘                      │  + MongoDB (port 27017) │                └────────────┘                └────────────┘
                                         └─────────────────────────┘
```

---

## Quick start

### 1. Prerequisites

- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`
- **MongoDB 7.x** running on `localhost:27017` — see [backend/MONGODB_SETUP.md](backend/MONGODB_SETUP.md)
- **LiteLLM proxy** on `localhost:4000` — see [LiteLLM Configuration](#litellm-configuration) below

### 2. Backend

```bash
cd axiom-q
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env       # edit values if needed

# IMPORTANT: run from axiom-q/ (not backend/), and use port 8081
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8081
```

Backend listens on `http://localhost:8081`. Interactive docs at `http://localhost:8081/docs`.

> **Two things that bite people:**
> - **Run from `axiom-q/`, not `axiom-q/backend/`** — otherwise you get `ModuleNotFoundError: No module named 'backend'`.
> - **Port must be `8081`.** The frontend `.env` hardcodes `http://localhost:8081` for the REST API and both WebSockets. The `--port` flag overrides `BACKEND_PORT` in `backend/.env`, so pass `8081` explicitly (or the live heatmap and telemetry won't load).

### 3. Frontend

```bash
cd axiom-q
npm install
cp .env.example .env       # edit values if needed

npm run dev                # http://localhost:5173
```

---

## Environment variables

Every value lives in `.env` — no hardcoded secrets in source.

### Backend — `backend/.env`

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `axiom_q` | Database name |
| `LITELLM_URL` | `http://127.0.0.1:4000/v1/chat/completions` | LiteLLM OpenAI-compatible endpoint |
| `LITELLM_API_KEY` | `freecc` | LiteLLM bearer token (NVIDIA API key lives in LiteLLM config) |
| `LITELLM_MODEL` | `ising-calibration` | Model name registered in LiteLLM |
| `LITELLM_REQUEST_TIMEOUT_SECONDS` | `60` | LiteLLM HTTP timeout |
| `BACKEND_HOST` | `0.0.0.0` | uvicorn bind host |
| `BACKEND_PORT` | `8000` | uvicorn bind port — **but run on `8081`** to match the frontend `.env` (pass `--port 8081` on the command line) |
| `FRONTEND_ORIGINS` | `http://localhost:5173,http://localhost:4173` | CORS allow-list (comma-separated) |

### Frontend — `.env` (repo root)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8081` | Base URL for REST calls |
| `VITE_WS_URL` | `ws://localhost:8081/ws/telemetry` | Quantum telemetry WebSocket endpoint |
| `VITE_PROSTHETIC_WS_URL` | `ws://localhost:8081/ws/prosthetic` | Prosthetic live-demo WebSocket endpoint |

`.env.example` is the template — copy it and edit. All three URLs must point at the same port the backend is running on (`8081`).

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Health check — returns Mongo + LiteLLM reachability |
| `/api/v1/qubits` | GET | List qubit configurations (8 auto-seeded on first run) |
| `/api/v1/calibrate/{qubit_id}` | POST | Run calibration via LiteLLM-routed NVIDIA Ising model |
| `/api/v1/telemetry/{qubit_id}` | GET | Latest in-memory telemetry record for a qubit |
| `/api/v1/history` | GET | Last N calibration-runs from MongoDB |
| `/api/v1/prosthetics/heatmap` | GET | Serves the latest generated pressure-grid heatmap PNG (the "LIVE VLM SCAN HEATMAP" image) |
| `/ws/telemetry` | WS | Bidirectional telemetry stream (send noise inputs → receive simulation probabilities) |
| `/ws/prosthetic` | WS | Prosthetic live-demo stream (lever/cell state → diagnosis + healing) |

Full interactive docs: start the backend, then visit `http://localhost:8081/docs`.

---

## How calibration works

1. Frontend establishes WebSocket to `/ws/telemetry`, streams slider values (`t1_relaxation`, `phase_damping`) every change.
2. Backend runs Qiskit Aer simulation (`backend/quantum_engine.py`) with those noise parameters on a 50-point Rabi sweep → returns noisy probabilities.
3. Backend persists telemetry to MongoDB (status `UNCALIBRATED`) and into in-memory `telemetry_store`.
4. When user clicks **Run Autonomous Calibration**, frontend POSTs `/api/v1/calibrate/{qubit_id}`.
5. Backend fetches the latest telemetry in-memory (fallback: Mongo), calls LiteLLM with the ising-calibration prompt, parses `drift_corrected_mhz` + `pi_pulse_amp_mod` + `confidence` JSON from the model's reply.
6. Backend persists `CALIBRATED` status + corrections to Mongo, broadcasts a clean Rabi waveform over WS, returns the payload to the UI.
7. Frontend smoothly animates the noise sliders back to 0, updates the agent payload inspector panel.

---

## LiteLLM Configuration

The LiteLLM proxy should expose the NVIDIA model via an OpenAI-compatible API. Example `config.yaml`:

```yaml
model_list:
  - model_name: "ising-calibration"
    litellm_params:
      model: "nvidia_nim/nvidia/ising-calibration-1-35b-a3b"
      api_base: "https://integrate.api.nvidia.com/v1"
      api_key: "nvapi-..."
      rpm: 40
      temperature: 0.2
      max_tokens: 32768
```

Start LiteLLM:

```bash
litellm --config config.yaml --port 4000
```

Quick smoke-test of the LiteLLM route without touching the full stack:

```bash
cd backend
python test_vlm_call.py
```

---

## Project layout

```
axiom-q/
├── .env / .env.example          # frontend env
├── package.json / vite.config.js
├── src/                         # Vite + React
│   ├── main.jsx, App.jsx, App.css, index.css
│   ├── store/useQuantumStore.js # Zustand global state
│   └── components/
│       ├── Header/
│       ├── HardwarePanel/       # qubit grid + noise sliders
│       ├── TelemetryPanel/      # Rabi chart + Bloch sphere (Three.js)
│       ├── AgentPanel/          # terminal stream + JSON inspector
│       └── ui/                  # ErrorBoundary, PanelCard, Skeleton, StatusBar
└── backend/
    ├── .env / .env.example
    ├── requirements.txt
    ├── MONGODB_SETUP.md         # ← full Mongo guide
    ├── main.py                  # FastAPI app + lifespan + CORS
    ├── db.py                    # motor (async MongoDB client)
    ├── telemetry_store.py       # in-memory fallback for live telemetry
    ├── quantum_engine.py        # Qiskit Aer Rabi oscillation simulation
    ├── nvidia_client.py         # LiteLLM-routed NVIDIA Ising call
    └── test_vlm_call.py         # standalone LiteLLM smoke test
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend health: `mongo_available: false` | Mongo not running | See [MONGODB_SETUP.md](backend/MONGODB_SETUP.md) |
| Backend health: `litellm_reachable: false` | LiteLLM not on port 4000 | `litellm --config config.yaml --port 4000` |
| Frontend: `Failed to fetch qubits` | Backend down or wrong `VITE_API_BASE_URL` | Verify backend with `curl http://localhost:8081/` |
| "LIVE VLM SCAN HEATMAP" shows only text, no image | Backend not on `8081`, or a stale backend on `8081` predating the heatmap route | Confirm with `curl http://localhost:8081/api/v1/prosthetics/heatmap -o /dev/null -w "%{http_code}"` → expect `200`. If `404`, restart the backend on `8081` from current code |
| `ModuleNotFoundError: No module named 'backend'` | uvicorn launched from `backend/` instead of `axiom-q/` | Run `uvicorn backend.main:app` from the `axiom-q/` directory |
| Calibration hangs > 60s | LiteLLM timeout or model cold-start | Check `LITELLM_REQUEST_TIMEOUT_SECONDS`, try `test_vlm_call.py` |
| Frontend boots but shows "Backend connection failed" | CORS blocked | Add your frontend origin to `FRONTEND_ORIGINS` |
