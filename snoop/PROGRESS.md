# SNOOP 2.1 implementation checkpoint

## Guided investigation update — 2026-09-14

- Shared strict-name eligibility now excludes different readable profile names
  regardless of context scores, model groupings or earlier keep constraints.
  Nameless accounts remain unresolved and do not seed automatic target pivots.
- Guided web/CLI rounds persist coverage, questions, answers and follow-up plans.
  Added the shared `briefing` command and browser briefing/interview/round views.
- Added source-grounded AI research suggestions, modern reasoning-model request
  parameters, explicit provider selection and analysis of sources without accounts.
- Fixed negative answers, correction input, apostrophes, preset upgrades, stale
  job terminal-event replay and accounts-only work accidentally spawning web searches.
- Verification: 115 tests passed in 5.75 seconds; Ruff passed; JavaScript syntax
  checked with Node; isolated headless Edge exercise passed desktop and 500px
  layouts, exact-name exclusion, guided answer/continuation and zero JS exceptions.
- Wheel and source distribution built successfully under `.testtmp/dist-guided`;
  existing `dist` releases were preserved. Installed `snoop` loads this checkout.
- Model/provider behavior was checked with mocks and official documentation;
  no claim of live GPT-6 access or real-world identity accuracy is made.
- Setup, provider choices, limitations and recording workflow: `RECORDING_GUIDE.md`.

Date: 2026-09-12

## Complete

- Web discovery and schema-v3 case continuity.
- Adaptive typed-action planner, ranked lead frontier, finite presets, and follow-up loop.
- Google via SerpAPI, Brave Search, honest fallback, and manual-assistance imports.
- Source/page/document/account ingestion with evidence provenance and uncertainty.
- Bounded relevant-site crawling, feeds, sitemaps, linked profiles, public archives,
  Common Crawl URL indexing, RDAP/DNS/certificate clues, image OCR, and Google Lens adapter.
- Identity-resolution changes for missing names, namesakes, overlaps, and competing
  membership hypotheses.
- Shared command registry and state across one-shot CLI, talk, and web.
- Persistent job control, pause/stop/continue, restart/resume, and clean Ctrl+C handling.
- Web workspace redesign and matching CLI/presenter modes.
- Offline end-to-end discovery fixture and regression scenarios.
- README, provider setup, method/command coverage, recording runbook, changelog, and
  editable-install diagnostics.

## Final verification

- `python -m ruff check snoop tests`: passed.
- `python -m pytest -q -p no:cacheprovider`: 79 passed (latest full run: 5.46 seconds).
- `python -m snoop evaluate --json`: 5 synthetic cases; precision 1.0, linked
  coverage 1.0, resolved coverage 0.6, with two deliberately unresolved cases. This
  small fixture is regression coverage, not a real-world accuracy estimate.
- Editable install: `snoop-osint 2.1.0`, loaded from this checkout; `snoop doctor`
  reports matching running and installed versions.
- Wheel: `dist/snoop_osint-2.1.0-py3-none-any.whl`, 38 entries, packaged data/web
  assets present.
- Source distribution: `dist/snoop_osint-2.1.0.tar.gz`, including the environment
  template, README, changelog, checkpoint, tests/fixtures, and package assets.
- Installed CLI: version, doctor, provider status, case listing, exact Google command
  unavailable-state, generated help, plain output, and command registration passed.
- Web: index/cases/providers/commands/case/plan endpoints passed on localhost; 44
  commands exposed, including explicit imports. Settled desktop and 500px narrow
  layouts were inspected in headless Microsoft Edge; a mobile hidden-workspace
  cascade and hero sizing issue found during that check were fixed. Reduced-motion
  and narrow CSS paths are present.
- Live search: Google via SerpAPI is configured and produced six bounded queries in the
  authorised self-investigation case (40 structured results total). A resumed live run
  stayed responsive, added six sources, emitted 19 job events, and stopped honestly when
  new information stalled. Brave remains unconfigured. Secret values were not logged.

Current optional blockers: `BRAVE_SEARCH_API_KEY` for Brave Search, `pypdf` for richer PDF extraction, and
Pillow + pytesseract + the Tesseract binary for image OCR. Core and mocked/offline
investigation paths are complete without them.
