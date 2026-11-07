# OSINT Toolkit Setup (Windows 11 Pro)

This workspace contains 8 OSINT engines, completely configured with isolated Python virtual environments:

1. **[Sherlock](https://github.com/sherlock-project/sherlock)** (`sherlock/`) - Hunt down social media accounts by username across 400+ platforms.
2. **[Maigret](https://github.com/soxoj/maigret)** (`maigret/`) - Collect dossiers on a person by username across 5,900+ sites (CLI + Web UI).
3. **[Osintgram](https://github.com/Datalux/Osintgram)** (`Osintgram/`) - Instagram OSINT investigation tool with interactive Web UI (FastAPI).
4. **[Numint](https://github.com/whoamitang/numint)** (`numint/`) - Phone number intelligence profiling, carrier inspection, spam score, and Web UI.
5. **[Snoop](https://github.com/whoamitang/snoop)** (`snoop/`) - Evidence-backed public persona and profile audit, identity linking, and browser case workspace.
6. **[Holehe](https://github.com/megadose/holehe)** (`holehe/`) - Check registered accounts by email across 120+ platforms without alerting the target.
7. **[GHunt](https://github.com/mxrch/GHunt)** (`GHunt/`) - Google / Gmail account OSINT framework.
8. **Indonesia OSINT Suite** (`indo_osint/`) - 16-digit NIK KTP decoder, 18-digit NIP ASN parser, Telco & E-Wallet VA generator, Plat Nomor TNKB decoder, PDDikti dorks, live Data Bocor (XposedOrNot) & Stealer (Hudson Rock) check, and offline SQLite FTS5 database search.

---

## 🚀 Quick Launch (Single All-in-One Launcher)

You only need **one file**:

- **`run.bat`** - **The All-in-One Master Launcher**:
  - Double-click to launch the Master Control Center (`app.py`).
  - Auto-provisions environments if needed on first launch.
  - Supports direct CLI commands (e.g. `.\run.bat sherlock user`, `.\run.bat indo --nik 3174...`, `.\run.bat indo --email target@mail.com`, `.\run.bat web maigret`).

---

## 📸 Osintgram: Connecting `instagrapi`

Osintgram needs a backend to fetch Instagram data. Since you want to use **`instagrapi`** (free backend), authenticate once:

### Method A: Browser Session ID (Recommended)
1. Log in to [instagram.com](https://www.instagram.com) in your browser.
2. Press `F12` -> **Application** (Chrome/Edge) or **Storage** (Firefox) -> **Cookies** -> `https://www.instagram.com`.
3. Copy the value of the `sessionid` cookie.
4. Run `.\run.bat` -> Option `[1]` Target Investigation -> Option `[5]` Instagram Recon -> Option `[2]` Login via Session ID, and paste it.

### Method B: Username & Password
1. Run `.\run.bat` -> Option `[1]` Target Investigation -> Option `[5]` Instagram Recon -> Option `[3]` Login via Credentials.
2. Enter username, password, and 2FA code if prompted.

---

## 💻 Command Line / Terminal Usage

From PowerShell or Command Prompt in the toolkit directory:

```powershell
# Master Menu:
.\run.bat

# Sherlock
.\run.bat sherlock <target_username>

# Maigret
.\run.bat maigret <target_username> -a
.\run.bat web maigret

# Osintgram Web UI
.\run.bat web osintgram

# Numint Phone OSINT
.\run.bat numint +6281234567890
.\run.bat web numint

# Snoop Persona Audit
.\run.bat snoop "Target Name"
.\run.bat web snoop

# Holehe Email OSINT
.\run.bat holehe target@example.com

# GHunt Google OSINT
.\run.bat ghunt email target@gmail.com

# Indonesia OSINT Suite & Data Bocor
.\run.bat indo --nik 3174011708950001
.\run.bat indo --email target@example.com
.\run.bat indo --db-search "Query"
.\run.bat indo --db-import path/to/file.csv
```
