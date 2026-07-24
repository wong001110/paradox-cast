# Take Note — User Testing and Deployment Follow-up

## Environment limitations

- **GitHub push:** the workspace began without a repository; local `main` was initialized in `paradox-cast/`. The available GitHub connector authenticates as `wong001110` but does not expose repository creation, and `gh` is unavailable. Each phase will be committed locally; create/connect `wong001110/paradox-cast` and add it as `origin` before pushing.
- **Live AI providers:** no provider credentials are supplied. The API therefore tests its mock runtime and credential masking only.
- **Cloudflare R2:** no bucket or deployment credentials are supplied. The R2 adapter contract and local adapter can be tested; signed uploads/downloads require deployment configuration.
- **Email invitations:** MVP uses invite links/codes and in-app semantics. Delivery-email testing remains future work.
- **Real multi-user load:** local tests verify behavior, not internet-facing WebSocket concurrency/load.
- **Mobile browsers:** automated Chromium smoke testing covers a desktop viewport first; test Android/iOS touch and small layout during user QA.

## User-test checklist

1. Connect a GitHub remote and confirm all local phase commits push to `main`.
2. Configure PostgreSQL and Cloudflare R2, then test private signed asset upload/download expiry.
3. Add a non-production API credential; confirm masked display and a real structured provider response.
4. Open two browsers with separate accounts; verify lobby updates, link/code joins, host rules, disconnect/rejoin, and manifest locking.
5. Test visual-novel playback and A/B comparison with the official assets at desktop and mobile widths.

