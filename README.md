# Paradox Cast — An AI Timeline Mystery Creator

Paradox Cast is an online, multiplayer AI timeline mystery creator. It presents an illustrated visual novel while a deterministic Python simulation authoritatively resolves intent, travel, encounters, observation, memory, replay, and explainable timeline branches.

## MVP boundaries

- **Included:** reusable character cards, scenario creator, database-backed lobbies, frozen run manifests, deterministic timeline simulation, visual-novel playback, external interventions, encrypted runtime credentials, OpenAI-compatible provider calls, R2-compatible asset storage, official art pipeline, and basic admin visibility.
- **Excluded:** free-roaming 2D gameplay, coordinate collision/tile maps, player-facing memory edit/delete/implant, theme editor/switching, and API keys in shared content.

## One-command local integration stack

Docker Compose starts PostgreSQL, MinIO as a local Cloudflare R2-compatible target, FastAPI, and the Vite client:

```bash
docker compose -f docker-compose.local.yml up --build
```

Open:

- App: `http://localhost:5173`
- FastAPI docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001` (`paradox` / `paradox-local-secret`)
- PostgreSQL: `localhost:5432` (`paradox_cast` / `paradox_cast`)

Use **Lobby** to test the real REST + WebSocket lobby flow. Open separate browser profiles, select different local identities, join the same code, bind each seeded character/runtime, mark everyone ready, and lock the run manifest.

Use **Integration lab** to confirm PostgreSQL connectivity, upload a file through a presigned S3 URL, open a signed download URL, save an encrypted provider credential, create a runtime profile, and ask the provider to select one legal simulation action.

Reset all local data with:

```bash
docker compose -f docker-compose.local.yml down -v
```

The credential key and MinIO credentials in `docker-compose.local.yml` are development-only values. Replace them before any shared deployment.

## Connect a real Cloudflare R2 bucket

Copy `backend/.env.example` to `backend/.env` or set the same variables in your deployment:

```bash
R2_BUCKET_NAME=your-bucket
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_PUBLIC_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_REGION=auto
R2_ADDRESSING_STYLE=path
```

Configure the R2 bucket CORS policy to allow `PUT` from the frontend origin with the `Content-Type` header. Browsers receive only short-lived presigned URLs; R2 credentials remain in the backend.

## Connect and run a real AI provider

Generate and keep a stable Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set it as `PARADOX_CAST_CREDENTIAL_KEY`. Supported adapters are:

- `deepseek` via `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com`)
- `openai` via `OPENAI_BASE_URL` (default `https://api.openai.com/v1`)
- `openai_compatible` via `OPENAI_COMPATIBLE_BASE_URL`
- `mock` for deterministic offline tests

Then use the product flow:

1. Open **Integration lab**.
2. Enter the provider, an available model ID, and a non-production API key.
3. Select **Save, test, and use in Lobby**. A successful runtime becomes the preferred host-funded runtime.
4. Open **Lobby**, create an AI lobby, and bind the host character to that runtime.
5. Other participants join and bind their character cards. They inherit the host-funded runtime without receiving the host credential.
6. Mark every cast member ready and select **Start AI run**.
7. The server freezes the Run Manifest, asks every bound runtime to select from server-generated legal actions, validates each answer, executes the result through the deterministic Python kernel, and opens the visual-novel replay.
8. Inspect **A · Original**, **B · Branch**, **Timeline**, and **A/B compare**.

Provider output cannot directly mutate simulation state. AI selects one action from a legal set supplied by the Python server. The kernel remains authoritative for routes, travel time, encounters, observations, dialogue effects, event ordering, replay, and timeline branching. If a configured provider fails, the local product flow records the failure and may use an explicit legal `wait` fallback.

## Manual local development

### Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The default database is SQLite. Set `DATABASE_URL=postgresql+psycopg://...` to use PostgreSQL.

### Frontend

```bash
cd web
npm install
npm run dev
```

The Vite app proxies `/api` to the backend during local development. Set `VITE_API_BASE_URL` when the API is served from another origin.

## Test the deterministic mock loop

Start the backend and frontend, then select **Run mock demo**. The button calls `POST /api/demo/run`, creates demo Character Cards, a Scenario, Lobby, ready cast, and frozen Run Manifest, and returns the authoritative original simulation and an explainable branched replay.

The UI opens the visual-novel player with the live manifest. Use **A · Original** and **B · Branch** to replay every simulation event in order. The deterministic mock demo needs no provider API key and remains available as an offline regression path.

## Official default artwork

Four canonical neutral portraits for the adult default cast are committed under `web/public/assets/characters/`. Prompt and asset contracts live in `assets/prompts/default-cast.json` and `assets/manifest.json`; derived expression portraits and final scenario backgrounds remain follow-up art coverage.

## Architecture

- `backend/`: FastAPI, SQLAlchemy, PostgreSQL/SQLite, provider and object-storage adapters, AI-run orchestration, and the authoritative simulation kernel.
- `web/`: React + TypeScript visual-novel application, local multiplayer lobby, AI runtime setup, and integration test surface.
- `docs/`: locked product constraints, specifications, assets, operations, and user-test notes.
- `assets/`: committed official default visual assets and manifests.

Production targets PostgreSQL and Cloudflare R2. The local Compose stack substitutes MinIO through the same S3-compatible adapter.

## Commands

```bash
make test
make lint
make web-test
make local-up
make local-down
```

See [`docs/TAKE-NOTE.md`](docs/TAKE-NOTE.md) for environment-sensitive verification.
