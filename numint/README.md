<div align="center">

# Numint

**Look up a phone number and get a clean intelligence profile.**

Works in your terminal, in a browser, or straight from Discord.

`git clone` → `pip install .` → `numint +14155550123`

</div>

---

## What it does

You give it a phone number. Numint tells you everything public it can find:

1. **Instant basics, no signup needed.** Using Google's `libphonenumber`, it checks if
   the number is real, what kind of line it is (mobile, landline, VoIP), every format,
   the country, region, carrier, and time zones.
2. **More detail from data providers.** If you add free API keys, it asks several services
   at the same time for carrier, line type, location, and a fraud/spam risk score.
3. **One clean profile.** When providers disagree, Numint keeps every answer and shows
   who said what, instead of hiding it. It also shows how confident it is.
4. **Finds accounts on the number.** It checks popular sites (Instagram, Amazon, Snapchat,
   Twitter/X, Microsoft) to see if the number is registered there, and grabs any masked hint
   the site leaks (like `j••@gm***.com`).
5. **Search links.** Ready-to-click links to look the number up on Google, social sites,
   reverse-lookup sites, and messaging apps.
6. **Optional AI summary.** Give it an OpenAI, Anthropic, or Gemini key and it writes a
   plain-language summary of what was found. It only talks about the data that was
   collected and never makes up names or identities.

It runs fine with **zero keys**. Keys just unlock more data.

## Sources

Numint pulls only from publicly available sources, including:

- **Number metadata** - validity, line type, every format, country, region, and time zones
- **Carrier information** - the mobile network or carrier behind the number
- **Spam reports** - fraud, spam, and reputation signals from risk-scoring services
- **Search results** - ready-to-use lookups across Google, Bing, and DuckDuckGo
- **Social media platforms** - account-presence checks and social search links

## Install

Numint installs from source. Clone the repo and install it with `pip`:

```bash
# 1. Clone the repo
git clone https://github.com/whoamitang/numint.git
cd numint

# 2. Install it (choose one)
pip install .              # basic (CLI only)
pip install ".[web]"       # with the web UI and API
pip install ".[all]"       # everything (web, PDF export, Discord bot)
```

> Tip: use a virtual environment first - `python -m venv venv && source venv/bin/activate`
> (on Windows: `venv\Scripts\activate`).

Prefer Docker? No Python setup needed:

```bash
git clone https://github.com/whoamitang/numint.git
cd numint
docker compose up          # then open http://localhost:8080
```

## Quick start

```bash
# Look up a number
numint +14155550123

# Find where it is registered online
numint +14155550123 --presence --yes-authorized

# Open the top lookup sites in your browser (does not scan)
numint +14155550123 --lookup

# Ask a plain question, answered only from what was found
numint +14155550123 --ask "is this a real mobile or a VoIP number?"

# Open the web app
numint web --port 8080

# Run the Discord bot
numint discord-bot
```

## Using the terminal

```bash
# Full lookup (runs every layer). Same as --all.
numint +14155550123

# Get raw JSON instead of the pretty view
numint +14155550123 --json

# Give a country hint for a local-format number
numint "020 7946 0958" --country GB

# Save a report (pick the format by file extension)
numint +14155550123 --output report.md      # or .json or .pdf

# Find accounts on the number (see the note below)
numint +14155550123 --presence --yes-authorized

# See which providers and keys are active
numint providers
```

### Choosing what runs

With no flags (or `--all`) every layer runs. To run just some layers, name them; they
combine.

```bash
numint +14155550123 --all          # everything, and lists the dorking links
numint +14155550123 --offline      # only the offline libphonenumber basics
numint +14155550123 --api          # only the API data providers
numint +14155550123 --ai           # only the AI summary
numint +14155550123 --api --ai     # API data plus the AI summary
```

A full scan (default or `--all`) also **lists** the search-engine dork links as text.
Opening sites in the browser is separate; see below.

### Scan a whole list (with a risk heatmap)

Put one number per line in a file (lines starting with `#` are ignored):

```bash
# Show only the colored risk grid
numint scan --input numbers.txt --heatmap

# Full report for each number, then the grid at the end
numint scan --input numbers.txt
```

The heatmap colors each number by risk (green, amber, red) so you can spot the bad ones
at a glance. Add `--presence --yes-authorized` to also fill the "accounts found" column.

## Using the web app

```bash
numint web --port 8080      # then open http://localhost:8080
```

The web app leads with the important stuff: the number, whether it is valid, its risk
score, and the accounts found on it. It also shows an **Open Sites** card with separate
buttons for the lookup sites and the dork searches (see below). Everything else (raw formats, carrier
detail, search links, provider status) is tucked under **Advanced details** so the page
stays clean. Tick **find accounts** to run the account check, or **send to Discord** to
push the result to your channel.

## Finding accounts on a number

The account check asks a few sites whether a number is already registered, by reading the
same response their signup or password-reset screens use. It never logs in, and it only
uses endpoints that do **not** text or email the person. The logic is based on the
open-source [`ignorant`](https://github.com/megadose/ignorant) project.

Sites checked right now:

| Site | Tells you |
| --- | --- |
| Instagram | registered or not, plus masked email/phone hint |
| Amazon | registered or not |
| Snapchat | registered or not |
| Twitter / X | registered or not |
| Microsoft | registered or not |

Because you are contacting real sites, this is opt-in. In the terminal you must add
`--yes-authorized` to confirm you are allowed to check the number. Sites change their
pages often, so a check may sometimes say `unknown` or `rate_limited`. That is normal.

Adding a new site is one file. Copy `src/numint/presence/_template.py`, rename it, and
fill in the check. It is picked up automatically.

## Opening sites in the browser

Inspired by the IntelTechniques phone tool. These flags do **not** run a scan; they just
fill URLs and open them in your browser for manual review (they never scrape or log in).
Lookup sites and dork searches are kept separate, and the top set is small so you are not
buried in tabs.

```bash
numint +14155550123 --lookup        # open the top 5 reverse-lookup sites
numint +14155550123 --lookup-all    # open every reverse-lookup site
numint +14155550123 --dorking       # open the top 5 search-engine dork searches
numint +14155550123 --dorking-all   # open every dork search
```

The top lookup sites are the handful that show the most and actually work (ThatsThem,
TruePeopleSearch, FastPeopleSearch, Whitepages, Sync.me). US and Canada numbers get the
people-search sites; other countries get the ones that work internationally. In the web
app, run a scan and use the **Open Sites** card, which has one button for lookup sites and
another for dork searches (your browser may ask to allow pop-ups). On a headless machine
with no browser, the links are printed so you can open them yourself.

Edit the lists any time: reverse-lookup sites live in `src/numint/data/lookup_sites.yaml`
and dork searches in `src/numint/data/dorking.yaml`. Each entry is one line with a
`top: true` flag for the small default set, so adding or removing one needs no code.

## Sending results to Discord

Two ways to connect Discord.

### 1. Webhook (push a result into a channel)

Fastest option. Make a webhook in your Discord channel settings, then:

```bash
numint config set DISCORD_WEBHOOK_URL https://discord.com/api/webhooks/xxxx/yyyy

numint +14155550123 --discord               # uses the saved webhook
numint +14155550123 --discord-url https://discord.com/api/webhooks/...   # one-off
```

Numint posts a tidy embed with the number, risk, and any accounts found. In the web app,
tick **send to Discord** (it uses the webhook you configured on the server).

### 2. Bot (run commands from Discord)

Want to type `/scan` in Discord and get results back? Use the bot.

```bash
pip install ".[discord]"
numint config set DISCORD_BOT_TOKEN your-bot-token
numint discord-bot
```

How to get a bot token:

1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Open the **Bot** tab, click **Add Bot**, and copy the token.
3. Open **OAuth2 > URL Generator**, tick `bot` and `applications.commands`, copy the
   invite URL, and add the bot to a server you control.
4. Run `numint discord-bot`. After it connects, the slash commands appear.

Commands:

- `/scan number:+14155550123` gives the profile as an embed.
- `/scan number:+14155550123 presence:true` also checks for accounts.
- `/providers` lists which providers are set up.

Keep the bot in a private server, since anyone who can see the channel can run lookups.

## Data providers

Every provider below has a real free tier. Numint uses whichever ones you set up and
skips the rest.

| Provider | Gives you | Free key |
| --- | --- | --- |
| **offline** (built in) | valid, type, formats, country, region, carrier, time zones | none needed |
| **Numverify** | valid, carrier, line type, location, country | https://numverify.com/product |
| **Veriphone** | valid, carrier, line type, region, country | https://veriphone.io/ |
| **AbstractAPI** | valid, format, country, region, carrier, line type | https://www.abstractapi.com/phone-validation-api |
| **NumLookupAPI** | carrier, line type, location, country | https://www.numlookupapi.com/ |
| **IPQualityScore** | fraud score, spam, disposable/VoIP, active status | https://www.ipqualityscore.com/create-account |
| **Twilio Lookup** (optional) | line type, caller name | https://www.twilio.com/try-twilio |

## Setting up keys

Keys are read from, in order: an environment variable, your user config file, or a project
`.env` file. The tool works with none set.

```bash
numint config set NUMVERIFY_API_KEY your_key_here
numint config set IPQS_API_KEY your_key_here

numint config list     # show configured keys (hidden values)
numint config path     # where the config file lives
```

## Turning on the AI summary

Pick one AI provider, set it plus its key, and the AI summary shows up automatically.
Leave it unset and everything else works the same.

```bash
numint config set AI_PROVIDER anthropic
numint config set ANTHROPIC_API_KEY sk-ant-...
numint config set AI_MODEL claude-sonnet-5      # optional
```

| `AI_PROVIDER` | Key | Default model |
| --- | --- | --- |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |
| `gemini` | `GEMINI_API_KEY` | `gemini-1.5-flash` |

The AI is told to reason only over the data Numint collected and to never invent names,
identities, or addresses. Unknown stays unknown.

## Adding your own data provider

Drop one file in `src/numint/providers/`. It is found automatically.

```python
# src/numint/providers/example.py
import httpx
from ..core.models import ParsedNumber, ProviderResult
from ..core.registry import register
from .base import BaseProvider

@register
class ExampleProvider(BaseProvider):
    name = "example"
    requires_key = True
    env_key = "EXAMPLE_API_KEY"
    signup_url = "https://example.com/get-key"

    async def _lookup(self, number: ParsedNumber, client: httpx.AsyncClient) -> ProviderResult:
        resp = await client.get("https://api.example.com/lookup",
                                params={"key": self.api_key(), "num": number.e164})
        resp.raise_for_status()
        data = resp.json()
        return ProviderResult(source=self.name, ok=True, raw=data, mapped={
            "carrier": data.get("carrier"),
            "line_type": data.get("type"),
            "country": data.get("country"),
        })
```

## How it is built

```
numint/
  core/            the shared engine used by the CLI, web, and Discord
    parser.py      offline libphonenumber basics
    engine.py      parse, ask providers at once, merge, find accounts, AI
    aggregator.py  merges answers and tracks conflicts and confidence
    footprint.py   builds the search links
    lookup.py      builds the reverse-lookup site links (--lookup)
    dorking.py     builds the search-engine dork links (--dorking)
    report.py      terminal view, Markdown/JSON/PDF export, batch heatmap
  providers/       one file per data source
  presence/        one file per account check (based on ignorant)
  integrations/    Discord webhook and bot
  ai/              OpenAI, Anthropic, Gemini adapters
  web/             the browser app and API
  cli.py           the command-line tool
```

## Development

```bash
pip install -e ".[web,dev]"
pytest
ruff check src tests
```

## License

MIT. See [LICENSE](LICENSE).

---

## Please use this responsibly

Numint only uses official APIs and public data. It does not scrape sites, break past
paywalls or geoblocks, or touch leaked or breach data. The lookup and dorking tools only
build URLs and open them in your browser for manual review; they never scrape or log in.

Only look up numbers you are allowed to look up, and follow the laws where you live and the
terms of service of each provider. This tool is for learning about OSINT and for defensive
security work. What you do with it is on you. The authors are not responsible for how you
use it, and provide it as-is with no warranty. Credit to the
[`ignorant`](https://github.com/megadose/ignorant) project for the account-check technique.
