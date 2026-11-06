# Changelog

## Unreleased — guided investigations

- Added shared exact-name eligibility and persisted exclusions, including protection
  against score/model overrides and automatic pivots from excluded or nameless accounts.
- Added guided checkpoints, answer-driven continuation, coverage briefings, interview
  history, cited observations and visible remaining work in web and CLI.
- Fixed negative candidate answers, correction flow, apostrophes in natural replies,
  CLI preset upgrades, deferred-work recovery and stale terminal-event replay.
- Added model-compatible reasoning parameters, explicit provider selection, source-only
  analysis and validated AI suggestions that become real bounded investigation actions.
- Fixed accounts-only mode accidentally scheduling web pivots and improved name phrase
  boundaries in search results and source mentions.
- Added offline regressions and a recording/model setup guide. Preserved existing
  model configuration, saved cases and uncommitted work.

## [2.1.0] - 2026-09-12

SNOOP now defaults to a persistent, evidence-backed web investigation instead of an
accounts-first username sweep.

### Investigation engine

- Added Google via SerpAPI and a separately labelled Brave Search adapter behind one
  paginated provider interface, plus explicit manual-result imports.
- Added a typed, ranked lead queue and adaptive planner with quick, standard, and deep
  budgets for searches, page reads, account probes, model calls, and pivot depth.
- Added source reading, bounded portfolio/site crawling, feeds and sitemaps, linked
  account expansion, public PDF extraction, Wayback/Common Crawl URL-index lookups,
  RDAP/DNS/certificate context, image OCR, and opt-in Google Lens lookups.
- Added schema-v3 persistence for queries, sources, evidence, leads, workflow state,
  budgets, identity membership hypotheses, and analyst decisions.

### Shared interfaces

- Added one typed command registry for the CLI, talk terminal, web buttons, and web
  command composer, including workflow control, discovery, evidence, graph, timeline,
  report, provider, and diagnostic commands.
- Rebuilt the web workspace around persistent cases, genuine backend events, source
  inspection, graph/timeline views, reconnectable jobs, narrow layouts, and reduced
  motion.
- Added quiet, plain-text, JSON, `NO_COLOR`, presenter, non-interactive, and clean
  cancellation behavior to the CLI.
- `snoop talk` now restores the latest case by default, honors every `--message`, and
  rejects unknown trailing input instead of silently ignoring it.

### Accuracy, continuity, and safety

- Missing profile names now remain `insufficient`; they are not called collisions.
  Namesakes, contradictory evidence, overlapping clusters, and competing account
  membership are represented separately from established ownership.
- Search snippets remain lead-only when an original page cannot be fetched. Mirrored
  pages, repeated queries/checks, and link cycles no longer inflate evidence.
- Case writes are atomic, completed work survives cancellation/restart, and pending or
  deferred leads remain available for continuation.
- URL retrieval keeps TLS verification, blocks private/metadata destinations and unsafe
  redirects, scopes credentials to exact origins, and treats page content as untrusted.
- Isolated PDF extraction in a killable worker, added per-lead and DNS deadlines, and
  made interrupted in-flight work resumable so malformed documents cannot freeze web.
- Background runs now emit a terminal event on completion or failure, while quiet
  operations emit honest heartbeats instead of leaving the interface spinning forever.

### Verification and packaging

- Added an offline end-to-end chain: indexed name mention -> portfolio -> unusual alias
  -> follow-up profile and PDF, discovered through the production planner interfaces.
- Added mocked regression coverage for unavailable pages, namesakes, provider fallback,
  CLI/web parity, resume/cancellation, provenance, prompt injection, unsafe fetching,
  archives/domains, document extraction, and OCR readiness.
- Added packaged web/data assets, PDF/OCR optional extras, editable-install guidance,
  provider configuration, recording walkthrough, and a secret-safe expanded `doctor`.

## [1.2.0] - 2026-09-04

Precision pass. The tool no longer offers up strangers who happen to share a
handle, and the output reads like a case file instead of a chat log.

### New — evidence engine (`snoop/evidence.py`)

Every account found is now scored for whether it is *actually the subject*
before anything is reported:

- **Handle specificity** — `theolindqvist` (full name) is strong evidence,
  `tlindqvist` is moderate, `theo` (a bare given name) is worth almost nothing.
- **Profile-name matching** — a profile carrying the subject's name scores
  heavily; a profile carrying a *different* full name is scored **negative** and
  named as such ("profile belongs to 'Kacper Nowak' - a different person").
- **Context matching** — `-c "canada"` / `-c "chess"`, or just telling it
  "he's from Toronto" in `snoop talk`, and every account already on file is
  re-scored instantly against it. No network round-trip.
- **Cross-account corroboration** — same profile photo (across *different*
  platforms only, ignoring generic site cards), shared email, one profile
  linking to another, a shared personal domain.

Accounts below the bar are **discarded as handle collisions** and reported
separately with the reason, rather than presented as possible matches. The AI
is now given the scored evidence, is forbidden from speculating from a handle
alone, and is required to say plainly when the subject was **not** found.

- `why did you discard the steam account?` is answerable — it explains the call.
- `snoop -c` is repeatable; the web UI has a context field.

### Changed — visuals

- Terminal output rebuilt as a **case file**: header block, scope/linked/
  discarded tally, one section per person, every account with its evidence
  itemised and scored, then an explicit DISCARDED section. No emoji, no
  progress bars, no chat styling.
- Web UI rebuilt to match — near-monochrome, monospace, evidence rows, a work
  log that shows verdicts as they land, a collapsed discard list, and a command
  line instead of chat bubbles.
- Accounts now carry a unique `ref` (`Strava·theo_lindqvist`), so two handle
  variants landing on the same platform can't be conflated.

### Fixed

- GitHub's generic OpenGraph card was being read as "same profile photo",
  falsely corroborating unrelated accounts.
- `stories.strava.com` was treated as a personal website; platform subdomains
  are now recognised, with the domain list derived from `sites.json`.

## [1.1.0] - 2026-09-04

Made it conversational and interactive, in the CLI and the web UI alike.

### New

- **`snoop talk`** — a REPL you steer in plain English: start an investigation,
  `dig deeper on his github` (pulls repos/languages/orgs; Reddit pulls recent
  subreddits + last-active date), `also check if she goes by X` (tries another
  handle, re-fuses), `pick A` / `merge A B` / `split A github`, or just ask a
  question about what's already been found - answered from evidence, no new
  fetching. Falls back to fixed patterns without an AI key.
- **Interactive identity cards** replace the flat identity list whenever 2+
  identities are found: each card shows confidence, accounts, the *alias
  breakdown* (spelling variants of a name grouped together, e.g. "Torvalds"
  vs "ToRvaLDs", vs a genuinely different name), and **cross-card overlap
  warnings** ("shares profile picture / similar name / same location with B")
  for identities that might actually be the same person after all.
  `snoop <target>` shows a hint to `snoop talk` when it finds more than one.
- **Web UI is now interactive too**: cards are clickable (pick a target, check
  two boxes to merge, click an account chip to deepen it) and a persistent
  chat bar at the bottom drives the same conversation as `snoop talk`, live,
  without reloading the page (`/api/talk` SSE endpoint).
- Identities are always labelled A/B/C… by confidence, and a platform the AI
  double-claims across two identities is settled deterministically (the
  higher-confidence one keeps it) before anything reaches the screen.
- Dossiers now carry `deep` (per-platform deep-dive facts) and `history` (the
  conversation transcript) alongside the existing hits/analysis.

## [1.0.0] - 2026-09-04

Full rewrite. The tool is now one thing done well: **identity investigation**.

### New

- **One pipeline.** `snoop <username | "real name" | email>` →
  resolve → enumerate ~65 platforms → open & read every profile →
  pivot on emails/links → AI identity fusion → dossier.
- **Real profile reading.** Found accounts are opened and parsed:
  dedicated JSON parsers for GitHub, GitLab, Docker Hub, Dev.to, Keybase,
  Reddit, Hacker News, Mastodon, Bluesky, Lichess, Chess.com, Gravatar,
  Mixcloud, Duolingo, Steam, Telegram, Linktree; OpenGraph / JSON-LD for the
  rest. Extracts name, bio, avatar, location, links, join date, followers.
- **AI analyst** clusters accounts into identities, separates namesakes,
  extracts name/location/occupation/aliases, flags contradictions, writes a
  confidence-scored summary. Auto-detects OpenAI / Claude / Gemini; degrades to
  a plain aggregate with no key.
- **Name → handle resolution** with ranked, convention-ordered guesses
  (handles nobiliary particles: `Guido van Rossum` → `gvanrossum`).
- **Email pivots**: Gravatar profile + linked accounts, HaveIBeenPwned breach
  exposure (with key), emails harvested from bios and GitHub.
- **Live streaming everywhere** — an event bus drives both the terminal live
  feed and the web UI over SSE.
- **Web UI** (`snoop web`): single page, dark, minimal. Live feed on the left;
  summary, identity cards, avatar face-grid, accounts grid, breach panel,
  next steps on the right. Past dossiers one click away.
- Dossiers are plain JSON in `data/dossiers/`.

### Removed

- The case-management shell, the multi-module orchestrator, the darkweb / dns /
  phone / crypto / dork modules, the REST API, PDF/DOCX export. The previous
  codebase is archived unchanged in `legacy/`.
- Dependency list cut to 5 packages (aiohttp, beautifulsoup4, lxml, rich,
  python-dotenv).
