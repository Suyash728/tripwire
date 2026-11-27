## What
<one or two lines>

Requirement IDs: <R1, R2 ... from docs/traceability.md>

## Definition of Done
- [ ] Works end-to-end on seed data ("Load sample case")
- [ ] Unit tests incl. at least one edge case; e2e/axe on the demo path
- [ ] Lint, format and types clean (ruff, eslint, prettier, tsc)
- [ ] Inputs validated; errors return the envelope
- [ ] a11y basics + axe clean
- [ ] Hot path cached or streamed
- [ ] Requirement IDs ticked in docs/traceability.md
- [ ] CI green; commit message names the requirement IDs

## Evidence
<paste raw output of `bash scripts/smoke_demo.sh` and anything notable from CI>
