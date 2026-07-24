# Paradox Cast — An AI Timeline Mystery Creator

Paradox Cast is an online, multiplayer AI timeline mystery creator. It presents an illustrated visual novel while a deterministic Python simulation authoritatively resolves intent, travel, encounters, observation, memory, replay, and explainable timeline branches.

## MVP boundaries

- **Included:** reusable character cards, scenario creator, lobbies, run manifests, deterministic timeline simulation, visual-novel playback, external interventions, runtime profiles, credential masking, official art pipeline, and basic admin visibility.
- **Excluded:** free-roaming 2D gameplay, coordinate collision/tile maps, player-facing memory edit/delete/implant, theme editor/switching, and API keys in shared content.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The API health endpoint is `http://localhost:8000/api/health` and interactive documentation is at `/docs`.

### Frontend

```bash
cd web
npm install
npm run dev
```

The Vite app proxies `/api` to the backend during local development.

## Test the real demo loop

Start the backend and frontend in separate terminals, then select **Run demo case** in the upper-right of the app. The button calls `POST /api/demo/run`, which creates demo Character Cards, a Scenario, Lobby, ready cast, and frozen Run Manifest before returning the authoritative original simulation and an explainable branched replay.

The UI opens the visual-novel player with the live manifest. Use **A · Original** and **B · Branch** to replay every simulation event in order, including character focus, location, source, timestamp, route or encounter metadata, and the external intervention that produced the branch. The separate Timeline and A/B Compare views remain available for inspection.

The demo deliberately uses the deterministic mock runtime and needs no provider API key.

## Official default artwork

Four canonical neutral portraits for the adult default cast are committed under `web/public/assets/characters/`. The React presentation uses these WebP portraits and retains a CSS portrait fallback for missing local assets. Prompt and asset contracts live in `assets/prompts/default-cast.json` and `assets/manifest.json`; derived expression portraits and final scenario backgrounds remain tracked as MVP follow-up coverage.

## Architecture

- `backend/`: FastAPI, SQLAlchemy, Pydantic and the authoritative simulation kernel.
- `web/`: React + TypeScript visual-novel user application and admin surfaces.
- `docs/`: locked product constraints, specifications, assets, operations and user-test notes.
- `assets/`: committed official default visual assets and manifests.

Production targets PostgreSQL and Cloudflare R2. Local development uses SQLite and a local asset-storage adapter. No browser receives raw R2 or provider credentials.

## Commands

```bash
make test
make lint
make web-test
```

See [`docs/TAKE-NOTE.md`](docs/TAKE-NOTE.md) for environment-sensitive verification.
