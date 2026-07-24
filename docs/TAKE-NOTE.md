# Take Note — User Testing and Deployment Follow-up

## Local integration coverage

`docker compose -f docker-compose.local.yml up --build` now provides:

- PostgreSQL as the active SQLAlchemy database
- MinIO through the same S3-compatible adapter used for Cloudflare R2
- presigned PUT and GET asset flows
- encrypted provider credential storage and OpenAI-compatible runtime calls
- development identities, scenario, cards, and mock runtime profiles
- REST lobby mutations plus database-backed WebSocket snapshots
- the React Integration Lab and real Lobby test surfaces

## Environment-sensitive checks

- **Real Cloudflare R2:** supply the R2 endpoint and bucket credentials, configure browser CORS for the frontend origin, upload a file, complete it, and open the short-lived download URL.
- **Real AI providers:** configure a stable `PARADOX_CAST_CREDENTIAL_KEY`, save a non-production API credential in Integration Lab, and confirm the selected action is one of the legal actions sent by the server.
- **Internet access:** network-provider tests require the local backend to reach the provider endpoint.
- **WebSocket scaling:** lobby snapshots are read from PostgreSQL and pushed over WebSocket, which is sufficient for local and small single-region testing. A high-scale deployment should add a shared pub/sub layer and load testing.
- **Mobile browsers:** automated checks cover code paths; verify Android/iOS touch, narrow layouts, file selection, and browser WebSocket behavior manually.

## User-test checklist

1. Start the Compose stack and confirm `/api/system/status` reports PostgreSQL and object storage as reachable.
2. Upload a small image from Integration Lab and open its signed download URL.
3. Save a provider API key, create a runtime, and confirm the provider selects a legal action without the raw secret appearing in the response.
4. Open two separate browser profiles, choose different local identities, create/join one lobby, bind characters/runtimes, toggle ready, and lock the manifest.
5. Run the deterministic demo and inspect original/branch visual-novel playback at desktop and mobile widths.
6. Replace MinIO variables with a real R2 bucket and repeat the asset test before deployment.
