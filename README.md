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

