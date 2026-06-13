# MongoDB Setup for Axiom.Q

The Axiom.Q backend uses MongoDB to persist:
- Qubit register configurations (`qubits` collection)
- Telemetry records (`telemetry` collection, status `UNCALIBRATED` → `CALIBRATED`)
- Calibration history (`calibration_history` collection)

**MongoDB is required for the qubit endpoint**, but the rest of the app degrades gracefully without it — calibration requests fall back to the in-memory `telemetry_store`, and warnings are logged.

---

## Option 1 — Docker (recommended)

Quickest, isolated, no system install required.

```bash
# From the repo root or any directory — the data volume is just a named path
docker run -d \
  --name axiom-q-mongo \
  -p 27017:27017 \
  -v "$(pwd)/.mongo-data:/data/db" \
  mongo:7
```

Verify it's up:

```bash
docker exec axiom-q-mongo mongosh --eval "db.adminCommand('ping')"
# Expected: { ok: 1 }
```

Stop / restart / remove:

```bash
docker stop axiom-q-mongo        # stop
docker start axiom-q-mongo       # restart
docker rm -f axiom-q-mongo       # delete (data volume persists)
```

---

## Option 2 — Native install (Windows)

1. Download **MongoDB Community Server 7.x** from <https://www.mongodb.com/try/download/community>
2. During install, choose **"Install MongoDB as a Service"** so it auto-starts on boot.
3. Default port `27017` is fine — matches `MONGODB_URI` in `.env.example`.
4. Verify:

   ```powershell
   # PowerShell
   Get-Service MongoDB
   # Status should be "Running" with StartType "Automatic"
   ```

To use **MongoDB Compass** (GUI): <https://www.mongodb.com/try/download/compass>
Connect to `mongodb://localhost:27017`, database `axiom_q`.

---

## Option 3 — Native install (macOS / Linux)

```bash
# macOS (brew)
brew tap mongodb/brew
brew install mongodb-community@7
brew services start mongodb-community@7

# Ubuntu / Debian
sudo apt-get install -y mongodb-org

# Arch
sudo pacman -S mongodb
sudo systemctl start mongodb
```

---

## Environment variables

Defined in [`.env.example`](.env.example):

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | Connection string. Use `mongodb://mongo:27017` in Docker Compose. |
| `MONGODB_DB_NAME` | `axiom_q` | Database name |

For MongoDB Atlas (cloud), set:

```env
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB_NAME=axiom_q
```

---

## What gets auto-seeded

On startup, [backend/db.py:43-48](../backend/db.py#L43) checks the `qubits` collection. If empty, it seeds **8 default qubits** (`Q0`–`Q7`) with frequencies spread 4.8–5.64 GHz, amplitudes 0.95–0.81, and T₁ decay 80–52 µs. No manual setup needed.

To **reseed manually**:

```bash
docker exec axiom-q-mongo mongosh axiom_q --eval "db.qubits.deleteMany({})"
# Then restart the backend — auto-seed runs again.
```

---

## Verifying Mongo is reachable from the backend

When the backend starts, look for either of these log lines:

```text
[INFO] MongoDB connected at mongodb://localhost:27017 (db=axiom_q)
[INFO] Qubits collection empty — seeding defaults...
[INFO] Seeded 8 qubits.
```

Or, if Mongo isn't running:

```text
[ERROR] MongoDB is NOT reachable at mongodb://localhost:27017: ...
[ERROR] Start MongoDB before running the server. The app will start but report mongo_available=false.
```

You can also hit the health endpoint after starting the backend:

```bash
curl http://localhost:8000/
# { "mongo_available": true, "litellm_reachable": true, ... }
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ServerSelectionTimeoutError` on startup | Mongo not running, or wrong `MONGODB_URI` | Start Mongo, verify with `mongosh` |
| Frontend shows `qubits_error: "mongodb_unavailable"` | Backend can't reach Mongo | Check backend logs, verify URI |
| `ECONNREFUSED 127.0.0.1:27017` | Mongo bound to wrong interface | Ensure `bindIp: 0.0.0.0` or `127.0.0.1` in `mongod.conf` |
| Atlas connection fails with auth error | Wrong credentials / IP not whitelisted | Atlas → Network Access → add your IP; verify username/password in URI |
