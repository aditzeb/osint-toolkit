# SNOOP

SNOOP looks up a name's public footprint. It searches, reads what it finds,
checks matching accounts, and saves everything as a resumable case with
sources attached. Built for checking your own footprint or consented privacy
audits, not for leaked passwords, account access, or secret harvesting.

## Install

Linux or macOS:

```bash
git clone https://github.com/whoamitang/snoop.git
cd snoop
python3 -m venv venv
. venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
snoop doctor
```

Windows PowerShell:

```powershell
git clone https://github.com/whoamitang/snoop.git
Set-Location snoop
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
snoop doctor
```

Needs Python 3.11+.

## Search setup

```dotenv
SERPAPI_KEY=your_serpapi_key
BRAVE_SEARCH_API_KEY=your_brave_key
```

Copy `.env.example` to `.env` and set one or both keys. Get a SerpAPI key at
<https://serpapi.com/search-api> and a Brave key at
<https://api-dashboard.search.brave.com/api-reference/web/search/get>. Without
a key, search just stays unavailable, nothing breaks.

## Use it

```text
snoop "Theo Lindqvist" --mode deep
snoop talk --case last
snoop web
```

`snoop TARGET` starts a full investigation. `snoop talk` opens a chat style
control loop for your newest case. `snoop web` opens the browser workspace at
127.0.0.1:8000. Run `snoop help` for every command.

## Checking your work

```powershell
python -m ruff check snoop tests
python -m pytest -q -p no:cacheprovider
```
