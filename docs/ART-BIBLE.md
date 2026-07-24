# Paradox Cast MVP Art Bible

## Intent and style anchor

The official MVP uses a **modern anime scrapbook / journal visual-novel** style: soft, slightly desaturated pastels; warm off-white paper; torn notebook edges; memo labels; restrained washi tape; rounded sticker details; and an everyday mystery atmosphere. The supplied visual references establish the desired density and composition only. They are not production assets and must not be shipped as-is.

The app always uses this single default theme in the MVP. There is no theme editor or theme switching.

## Character guardrails

The four default characters are petite adult anime women. Their stated ages are fixed: Hana (23), Rei (25), Mira (21), Kagura (26). Keep them small-stature, cute and youthful in styling, in modern casual outfits, and non-sexualized. Do not use school uniforms, school settings as age coding, child proportions, or age-ambiguous language.

## Locked style anchor

Before generating final portraits, approve one full-body neutral reference for each character. All expressions, bust crops and lobby thumbnails must be derived from that approved reference; never regenerate a new identity per expression. Lock: hair silhouette, eye colour, outfit palette, accessory count, body scale, lighting direction, and portrait framing.

## Required asset set

| Group | Required files | Fallback |
| --- | --- | --- |
| Characters | `neutral`, `happy`, `thinking`, `concerned` expression portraits for all four cast members | `neutral` portrait, then the SVG colour-card silhouette |
| Backgrounds | `safehouse-lounge-day`, `safehouse-lounge-night`, `old-station-evening`, `cafe-nocturne` | CSS illustrated scene plus `assets/decor/paper-grain.svg` |
| Decoration | paper grain, tape, star, fragment-label, seal | CSS colour and shape fallback |
| Review | one contact sheet per character and one background contact sheet | fail validation before publishing asset version |

## Generation workflow

1. Generate and approve the four neutral references first.
2. Run derived portrait prompts against only the approved character reference.
3. Generate backgrounds with the same style anchor and no readable in-world text.
4. Build contact sheets and a reviewer checklist. Reject identity drift, age ambiguity, detached hands, unreadable composition, missing transparent backgrounds, or framing drift.
5. Add generated files and checksums to `assets/manifest.json`; validate required expression coverage before release.

## Prompt template

`Modern anime visual-novel portrait of {name}, a petite adult woman age {age}, {role}; {identity details}; modern casual outfit; non-sexualized; soft pastel scrapbook mystery mood; warm diffused indoor lighting; clean transparent background; waist-up, facing 3/4 left; consistent with the locked canonical neutral reference; no text, no logo, no school uniform, no child coding.`

Negative prompt: `minor, child, school uniform, sexualized pose, lingerie, logo, watermark, text, extra fingers, cropped face, different hairstyle, different eye colour`.

## Storage and release contract

Production objects belong in Cloudflare R2 under immutable versioned keys such as `official/v1/characters/rei/neutral.webp`. PostgreSQL owns metadata, visibility and version references. Private uploads use server-generated short-lived R2 URLs; browsers never receive R2 secrets. The checked-in `assets/` directory contains the public MVP manifest and local fallbacks only.

## Current implementation status

The visual-novel shell has intentionally committed CSS illustration and SVG decoration fallbacks so it remains usable without an image generation service. Final AI-generated reference portraits/backgrounds have not been created in this environment. See `docs/TAKE-NOTE.md` for the human review and generation handoff.
