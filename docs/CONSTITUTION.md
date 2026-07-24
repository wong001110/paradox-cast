# Paradox Cast Constitution

## Authority order

This Constitution is authoritative over the Product Bible, then technical specifications, phase tasks, and implementation. A lower layer may clarify but must not silently change a higher layer.

## Invariants

1. **Python is authoritative.** An AI runtime proposes high-level intent; it never authoritatively resolves legality, timing, travel, encounters, state, replay, branches, or outcome evaluation.
2. **A character card is reusable identity, never scenario state.** Scenario roles, secrets, relationships, inventory, location, and current memories belong to Scenario Characters.
3. **Credentials are secrets.** They never enter card exports, share payloads, snapshots, prompts, logs, or browser responses. Persisted display is masked.
4. **Branches must be explainable external interventions.** Direct generic memory edit/delete/implant is forbidden in MVP gameplay.
5. **The player sees a visual novel, not a free-roaming 2D game.** Coordinates, collision, tile maps, and real-time navigation are out of scope.
6. **One default art theme only.** Modern anime scrapbook / journal, with clearly adult, non-sexualized default cast styling.
7. **Private content is private by default.** Admin observability must not casually reveal private content.
8. **Cloudflare R2 is the deployment asset-storage direction.** Clients use application-issued, short-lived access rather than raw R2 credentials.

## Change policy

Any change to an invariant requires an explicit revision to this document and an update to affected specifications and tests.

