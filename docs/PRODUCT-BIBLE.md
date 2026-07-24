# Product Bible

## Purpose

Paradox Cast lets people author a structured mystery or social scenario, bring reusable AI-driven character cards into a lobby, observe one original timeline, and create explainable A/B branches from a frozen snapshot.

## Domain language

- **Character Card:** versioned long-term identity owned by a user.
- **Scenario Character:** scenario-bound cast instance that adds role, goals, secrets, beliefs, relationships, location, constraints, and optional runtime override.
- **Runtime Profile:** model/provider behavior configuration without a secret.
- **Credential:** encrypted provider secret referenced by a runtime grant.
- **Run Manifest:** immutable start-of-run record of scenario/card versions, cast, runtime bindings, rules, seed, asset versions, and intervention rules.
- **Intervention:** an external, auditable change such as revealing evidence, redirecting/delaying delivery, changing an item/start condition, or swapping a runtime.

## Experience

The default theme presents illustrated locations, adult-anime portraits, dialogue and narration in paper panels, a timeline strip, relationship/investigation notes, and an A/B comparison view. A lobby is the required entry point of a shared run.

## MVP creator boundaries

Included: Character Cards and Custom Scenarios. Not exposed: theme editor, theme switching, player-facing memory surgery.

## Open questions retained for later deployment

Provider key-management service, email delivery vendor, moderation policy workflow, Postgres/R2 production credentials, and live billing limits are implementation/deployment choices that do not alter the MVP's core rules.

