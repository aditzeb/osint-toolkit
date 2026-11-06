# Guided investigations and recording setup

This update makes SNOOP a resumable interview and evidence workspace. Start with
your own public footprint, an opted-in subject, or synthetic fixtures. The length
comes from real searches, source reading, questions and follow-up work. There are
no artificial delays or promises of exhaustive coverage.

## Start here

From the project directory in PowerShell:

```powershell
.\venv\Scripts\snoop.exe doctor
.\venv\Scripts\snoop.exe web
```

Open the localhost address printed by SNOOP. Enter the full name, select **deep**,
check **This is the exact full name**, and leave **Guided investigation** enabled.
Add known public context if available. Start the investigation.

The equivalent terminal workflow is:

```powershell
.\venv\Scripts\snoop.exe "Theo Lindqvist" --exact-name --guided --mode deep
.\venv\Scripts\snoop.exe talk --case last
```

Inside `talk`, answers such as `Toronto`, `I don't know`, `not relevant`, and
`actually Corrected Full Name` update the saved interview. In guided mode, an
answer automatically resumes available work. `Skip` is saved and the question
does not repeat. Direct commands remain available during the interview.

## What exact name means

- Matching normalizes case, Unicode composition, whitespace and punctuation.
  Initials, name particles, diacritics and word order remain significant.
- Different readable profile names go into **Excluded accounts**, regardless of
  matching handles, context scores, model output or an earlier Keep decision.
- Accounts without readable names stay under unresolved information. They are
  not exact-name identity cards and do not generate automatic account pivots.
- Search results need the full name as a phrase in their title or snippet for a
  full-name query. A surname, a fuzzy given name, or words scattered across a
  result are insufficient. Rejected results remain inspectable.
- Exact matches can still be namesakes. Context and corroborating sources are
  needed to establish attribution. The subject card remains separate.
- A spelling correction preserves the original input, reassesses accounts and
  supersedes pending automatically planned work for the old spelling.

## Guided rounds

Quick, standard and deep review progress after 4, 6 and 8 completed actions,
respectively. They ask one useful question when an answer can help: spelling,
candidate relevance, an unavailable profile, country/city, occupation, or a known
public username/profile. They continue when no useful unanswered question remains.

Each checkpoint saves coverage, gaps and upcoming actions. The briefing shows
source domains, actual read/unavailable outcomes, cited observations, candidate
exclusions, resource usage and the remaining frontier. The interview history
records your decisions separately from source evidence.

Configured AI reviews can analyze ordinary public mentions even when no account
has been found. Recommendations enter the real lead queue only after validation:
search terms must occur in cited evidence and source URLs must already be cited.
The engine rejects invented terms, unknown citations and excluded-account pivots.
Suggestions use the same deduplication and resource ceilings as other work.

| Preset | Searches | Page/document fetch units | Account probes | AI review calls | Pivot depth |
|---|---:|---:|---:|---:|---:|
| quick | 8 | 12 | 45 | 4 | 1 |
| standard | 18 | 30 | 110 | 10 | 2 |
| deep | 40 | 60 | 200 | 20 | 3 |

These are case resource limits, not runtime promises or completion percentages.
Compound methods can issue several HTTP requests per action. Explicit manual
commands and conversational AI routing/answers are separate from automatic review
budgets. Inspect provider billing for actual usage.

`run --preset deep` upgrades a smaller case and resumes work that fits the new
limits without resetting spent counters. Pause/stop preserve completed work. Run
and Continue do not silently ignore an unanswered question.

## Model and API configuration

Verified against official provider documentation on September 14, 2026.

For the strongest OpenAI analysis option, use **GPT-6 Astra**. For a balance of
cost and intelligence, use **GPT-5.6 Terra**. These are recommendations for this
workflow, not a SNOOP benchmark. Current model access depends on your API account.
See [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) and
[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra).

Edit the existing local `.env`; preserve your current secret values. The settings
below are an example, not a file to paste over an existing configuration:

```dotenv
SNOOP_AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-6-astra
SNOOP_REASONING_EFFORT=high
SNOOP_AI_MAX_OUTPUT_TOKENS=16000
SNOOP_AI_TIMEOUT=180
SNOOP_WORKFLOW_PRESET=deep

SERPAPI_KEY=your_serpapi_key
SNOOP_SEARCH_ENGINE=google
SNOOP_SEARCH_FALLBACK=1
# Optional second search index:
BRAVE_SEARCH_API_KEY=your_brave_search_key
```

Use `medium` reasoning for a more responsive interview; try `high` for a careful
recorded investigation. Higher reasoning can add latency and token cost. SNOOP's
OpenAI analysis uses Chat Completions with JSON output and model-compatible
reasoning parameters, without unsupported temperature settings for GPT-5/6.
The model does not fetch the internet itself; SNOOP's search and retrieval tools do.

| Key | What it contributes | Priority |
|---|---|---|
| `SERPAPI_KEY` | Google search results through SerpAPI | Primary discovery |
| `OPENAI_API_KEY` | Evidence interpretation, cited follow-up suggestions and conversational control | Recommended |
| `BRAVE_SEARCH_API_KEY` | A second search index; configured fallback and explicit cross-checks | Useful addition |
| `GITHUB_TOKEN` | Authenticated access to supported public GitHub API methods | Optional for GitHub-heavy cases |
| `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` | Alternative analysis provider | Choose one provider; extra keys do not combine models |

Create keys through [OpenAI's API setup](https://developers.openai.com/api/docs/quickstart),
[SerpAPI](https://serpapi.com/search-api), and
[Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started).
Keep keys in `.env`, never in the browser composer or recording. `doctor` and
`providers` report readiness and model names without printing values.

The strongest model cannot recover unavailable source content or turn a same-name
result into proof. Good search coverage and a known public anchor often improve a
case more than increasing reasoning effort alone.

## Optional document features

```powershell
.\venv\Scripts\python.exe -m pip install -e ".[pdf,ocr]"
```

PDF support uses `pypdf`. OCR additionally needs the Tesseract application installed
and available on PATH; the Python extras alone do not install that application.
OCR reads image text and is not facial identification. `doctor` reports readiness.
No OCR dependency is necessary for normal text-page research.

## Recording walkthrough

1. Show `providers` and the starting name/context. Explain the exact-name checkbox.
2. Run a deep guided investigation. Show actual queries and source outcomes in the
   event feed, then open a source and inspect its evidence record.
3. Answer a checkpoint question and show the new context-specific searches.
   If a candidate is a namesake, answer `not relevant` and show its exclusion.
4. Open **Interview history**, **Investigation rounds**, and **briefing**. Compare
   source-backed observations with the labelled AI interpretation and remaining gaps.
5. Inspect a discovered public account with `evidence H01`, `verify H01`, or
   `deepen H01`; use the references actually present in your case.
6. Cross-check a query explicitly on Brave with
   `search --engine brave --query '"Full Name"'` when configured. Imports via
   `manual-search` stay labelled manual assistance.
7. Explore `sources`, `queries`, `leads`, `aliases`, `compare`, `graph`, and
   `timeline`. Use `read URL`, `document URL`, `archive URL`, or `domain DOMAIN`
   when a discovered source makes the action relevant.
8. Pause, resume the saved case in `talk`, then show `report` and `export --redact`.
   Preview exported content before recording; presenter mode masks known case
   identifiers but is not a guarantee that all free-text personal information is removed.

Run `snoop help` for the authoritative shared command list. A sparse public
footprint can end early; record what is missing and why instead of implying more
coverage than the tools actually achieved.

## Verification scope

New tests use synthetic names and mocked providers. Browser checks use an isolated
localhost fixture and exercise the actual UI, SSE, case persistence and interview
code. These checks establish behavior, not real-world identity accuracy or live
access to a particular model/provider.
