# 🔍 OSINT Toolkit for Windows 11 (Global + Indonesia Edition)

[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Multi--License-informational.svg)](LICENSE)
[![Engines](https://img.shields.io/badge/OSINT%20Engines-8%20Integrated-success)](#-included-engines--upstream-credits)
[![Status](https://img.shields.io/badge/Status-Turnkey%20Ready-brightgreen)](#)

A turnkey, pre-configured **Open-Source Intelligence (OSINT)** suite for Windows 11. 

This repository bundles and integrates **eight OSINT engines**—combining seven industry-standard global reconnaissance tools with a built-in **Indonesia OSINT & Data Bocor Intelligence Suite (`indo_osint`)**—complete with isolated virtual environments, a **single unified Windows launcher (`run.bat`)**, an interactive Master Control Center (`app.py`), and modern graphical Web dashboards.

---

## 📦 Included Engines & Upstream Credits

This suite integrates seven open-source projects alongside a custom Indonesian regional intelligence & breach package. All core search capabilities, database definitions, and API clients belong to their respective original authors and maintainers. Full attribution is listed below:

| Engine | Upstream Repository | Author / Maintainers | License | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Sherlock** | [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) | Siddharth Dushantha & team | MIT | Fast username scanner checking 400+ social networks and web services. |
| **Maigret** | [soxoj/maigret](https://github.com/soxoj/maigret) | Soxoj | MIT | Deep username dossier profiling across 5,900+ sites with graph reports and built-in Web UI. |
| **Osintgram** | [Datalux/Osintgram](https://github.com/Datalux/Osintgram) | Giuseppe Criscione (Datalux) | GPLv3 | Interactive Instagram reconnaissance suite featuring an AI-assisted FastAPI Web Dashboard. |
| **Numint** | [whoamitang/numint](https://github.com/whoamitang/numint) | whoamitang & team | MIT | Professional phone number OSINT: carrier lookup, line type, spam risk score, registered accounts, and Web UI. |
| **Snoop** | [whoamitang/snoop](https://github.com/whoamitang/snoop) | whoamitang & team | MIT | Conservative, evidence-backed public profile audit, identity linking, document analysis, and case workspace. |
| **Holehe** | [megadose/holehe](https://github.com/megadose/holehe) | Palenath (megadose) | GPLv3 | Checks if an email address is registered across 120+ sites (Twitter, Instagram, Spotify, Adobe, etc.) without alerting the target. |
| **GHunt** | [mxrch/GHunt](https://github.com/mxrch/GHunt) | mxrch | AGPL-3.0 | Offensive Google / Gmail framework extracting GAIA ID, Maps reviews, Calendar, Photos, and Drive artifacts. |
| **Indo OSINT** | `indo_osint/` (Built-in) | OSINT Toolkit Contributors | MIT | Indonesian Regional & Data Bocor Intelligence: 16-digit NIK KTP decoder, 18-digit NIP ASN parser, Telco & E-Wallet VA generator, Plat Nomor TNKB decoder, PDDikti dorks, live XposedOrNot breaches & Hudson Rock infostealers, and offline SQLite FTS5 database search. |

---

## ✨ Features

- **Single All-in-One Windows Launcher (`run.bat`)**: One launcher to rule them all. Double-click to open the full interactive Master Control Center, or run any tool directly via CLI arguments (`run.bat sherlock`, `run.bat maigret`, `run.bat indo`, etc.).
- **Isolated Virtual Environments (`.venv`)**: Each external engine maintains its own isolated Python virtual environment, eliminating dependency version conflicts (e.g. `pydantic`, `aiohttp`, `fastapi`, `httpx`, `pillow`).
- **Target-Oriented Investigation Workflows**:
  - **Username Reconnaissance**: Sherlock (400+ platforms), Maigret (5,900+ sites), or automatic Dual-Engine sequential scans.
  - **Email Intelligence & Data Bocor**: Triple-threat reconnaissance combining Holehe (120+ sites), GHunt (Google Account artifacts), and live Data Bocor checks (XposedOrNot + Hudson Rock Infostealers + GitHub profile linking).
  - **Phone Number Intelligence**: Global Numint profile + Indonesian cellular operator, PSTN landline area codes, and E-Wallet Virtual Account name-resolution numbers.
  - **Indonesian Regional Intelligence (`indo_osint`)**:
    - **NIK KTP 16-Digit Decoder**: Extracts Province (38 provinces), Kabupaten/Kota (514 regencies/cities), Kecamatan (live Kemendagri Dukcapil API lookup), Gender, Birthdate, Age, Javanese Weton/Pasaran, Zodiac, Generation, and sequence number.
    - **NIP ASN / PNS 18-Digit Decoder**: Extracts Birthdate, CPNS Appointment Year/Month (TMT), years of service, BUP retirement year, and gender.
    - **Indonesian Phone & E-Wallet VA Generator**: Identifies cellular operators (Telkomsel, Indosat, XL, Axis, Tri, Smartfren) and 80+ PSTN landline area codes, generates Virtual Account codes for **DANA, OVO, GoPay, ShopeePay, and LinkAja**, and builds Indonesian fraud/marketplace dorks.
    - **Indonesian License Plate (Plat Nomor / TNKB) Decoder**: Maps all regional codes (`A`–`PY`), decodes Jadetabek (`B`) city sub-codes and vehicle classifications, and links to regional E-Samsat portals.
    - **Indonesian Public Registry Dorks**: Generates targeted queries for **PDDikti** (students/lecturers), **Putusan Mahkamah Agung** (court verdicts), **SIPP Pengadilan**, **LPSE** government procurement, and **AHU Kemenkumham** company records.
    - **Live Data Bocor & Infostealer Intelligence**: Real-time breach lookup across 480+ databases (Tokopedia, Bukalapak, Bhinneka, RedDoorz, etc.) and infostealer malware infection history via Hudson Rock.
    - **Private Offline Local Database (SQLite FTS5)**: Drop any private or investigation CSVs into `data/` and perform instant sub-second Full-Text Search across NIK, Phone, Name, Email, and Plate.
- **Web Dashboards Hub**:
  - **Maigret Web UI** on port `5000`
  - **Osintgram Web Dashboard** on port `8000`
  - **Numint Web Dashboard** on port `8080`
  - **Snoop Web Workspace** on port `8005`
  - **One-Click Multi-Launch**: Start and monitor all 4 dashboards simultaneously.

---

## 🚀 Quick Start (Windows)

### 1. Prerequisites
- **Windows 10 / 11 (64-bit)**
- **Python 3.11+** installed and added to `PATH` (download from [python.org](https://www.python.org/downloads/) or via Windows Terminal: `winget install Python.Python.3.13`).

### 2. Clone Repository
```cmd
git clone https://github.com/aditzeb/osint-toolkit.git
cd osint-toolkit
```

### 3. Launch
Simply double-click **`run.bat`**!  
On the very first launch, `run.bat` automatically detects missing environments, asks to run setup, provisions all virtual environments, and opens the Master Control Center!

---

## 🎮 How to Use

### 🌟 All-in-One Master Navigator (`run.bat`)
Double-click **`run.bat`** to open the interactive menu:

```text
============================================================================
   🔍  OSINT TOOLKIT - ALL-IN-ONE MASTER CONTROL CENTER (WINDOWS 11)   
   Sherlock | Maigret | Osintgram | Numint | Snoop | Holehe | GHunt | ID
============================================================================
 📍 Navigation: Main Navigation
----------------------------------------------------------------------------
Select an operation mode to begin:

 [1] 🎯 TARGET INVESTIGATION       (Guided search: Username, Email/Breaches, Phone, NIK, etc.)
 [2] ⚙️  INDIVIDUAL WORKSPACES      (Direct CLI for Sherlock, Maigret, Holehe, GHunt, etc.)
 [3] 🌐 WEB DASHBOARDS HUB         (One-Click Launch: Ports 5000, 8000, 8080, 8005)
 [4] 📁 EVIDENCE & REPORTS LOCKER  (View generated HTML/CSV/XLSX intelligence)
 [5] 🩺 HEALTH & SYSTEM DIAGNOSTICS(Verify all 8 venvs, run setup, or open shell)

 [0] 🚪 Exit Application
----------------------------------------------------------------------------
```

---

### 💻 Command-Line Direct Aliases (`run.bat <command>`)

You can run any tool or guided workflow directly from PowerShell or Command Prompt using **`run.bat`**:

#### 1. Username Reconnaissance
```powershell
.\run.bat sherlock target_username
.\run.bat maigret target_username
.\run.bat maigret target_username -a        # Scan all 5,900+ sites
.\run.bat --username target_username        # Dual Sherlock + Maigret scan
```

#### 2. Email Intelligence, Data Bocor & Google OSINT
```powershell
.\run.bat holehe target@example.com
.\run.bat holehe --only-used target@example.com
.\run.bat ghunt email target@gmail.com
.\run.bat --breach target@example.com       # Live Data Bocor & Infostealers check
.\run.bat --email target@example.com        # Holehe + GHunt email scan
```

#### 3. Phone Number & E-Wallet VA
```powershell
.\run.bat numint +6281234567890
.\run.bat indo --phone 081234567890         # Telco, PSTN region & DANA/OVO/GoPay/Shopee VA
.\run.bat --phone +6281234567890           # Combined Numint + Indo OSINT scan
```

#### 4. Indonesian Regional OSINT Suite
```powershell
.\run.bat indo                              # Interactive Indonesian CLI Menu
.\run.bat indo --nik 3174011708950001       # 16-digit NIK KTP Decoder
.\run.bat indo --nip 199008172019031005     # 18-digit NIP ASN / PNS Parser
.\run.bat indo --plate "B 1234 KAA"         # Vehicle License Plate & E-Samsat
.\run.bat indo --dorks "Target Name"        # PDDikti, Mahkamah Agung, LPSE & AHU
.\run.bat indo --email target@email.com     # Live Data Bocor (XposedOrNot) & Stealers
.\run.bat indo --db-search "Budi"           # Offline Private Database FTS5 Search
.\run.bat indo --db-import my_data.csv      # Fast FTS5 Indexer for local datasets
.\run.bat indo --db-stats                   # View private database statistics
```

#### 5. Persona Footprint & Case Investigation
```powershell
.\run.bat snoop "Target Name"
.\run.bat snoop "Target Name" --mode deep
```

#### 6. Web Dashboards & Utilities
```powershell
.\run.bat web maigret                       # Launch Maigret Web UI (Port 5000)
.\run.bat web osintgram                     # Launch Osintgram Web UI (Port 8000)
.\run.bat web numint                        # Launch Numint Web UI (Port 8080)
.\run.bat web snoop                         # Launch Snoop Web Workspace (Port 8005)
.\run.bat web all                           # One-Click Launch ALL 4 Web Dashboards
.\run.bat --diag                            # System Health & Virtual Environment Status
.\run.bat setup                             # Run Automated Setup Wizard
```

---

## 📸 Osintgram: Instagram Setup (`instagrapi`)

Osintgram uses Instagram data backends. To use the built-in free `instagrapi` backend, authenticate once:

> ⚠️ **Important Security Tip**: Always use a secondary / throwaway Instagram account for OSINT research. Never use your personal primary account.

1. Log in to [instagram.com](https://www.instagram.com) in Chrome, Edge, or Firefox.
2. Press **`F12`** $\rightarrow$ go to **Application** (Chrome/Edge) or **Storage** (Firefox) $\rightarrow$ **Cookies** $\rightarrow$ `https://www.instagram.com`.
3. Locate the cookie named **`sessionid`** and copy its value.
4. Run `.\run.bat` $\rightarrow$ Option `[1]` Target Investigation $\rightarrow$ Option `[5]` Instagram Recon $\rightarrow$ Option `[2]` Login via Session ID, paste the `sessionid`, and press Enter.

---

## 📁 Repository Structure

```text
OSINT-Toolkit/
├── run.bat                        # ALL-IN-ONE MASTER WINDOWS LAUNCHER
├── app.py                         # Master Control Center (guided workflows & hub)
├── reports/                       # Centralized evidence locker for generated dossiers
├── data/                          # Local private database directory (.gitignored)
│   └── local_osint.db             # Offline SQLite FTS5 database (.gitignored)
├── .gitignore                     # Strict exclusion of sessions, credentials & caches
├── README.md                      # Documentation & Upstream Credits
├── README_SETUP.md                # Detailed setup guide
│
├── indo_osint/                    # Indonesia OSINT & Data Bocor Intelligence
│   ├── cli.py                     # Interactive CLI & command-line flags
│   ├── breach_lookup.py           # Live Data Bocor (XposedOrNot) & Stealer (Hudson Rock) API
│   ├── db_search.py               # Fast local SQLite FTS5 search & CSV importer
│   ├── nik_parser.py              # 16-digit NIK KTP decoder + Kemendagri lookup
│   ├── phone_intel.py             # Telco prefix, PSTN area code & E-Wallet VA generator
│   ├── plate_decoder.py           # TNKB Plat Nomor region/sub-region decoder
│   ├── registry_dorks.py          # 18-digit NIP ASN parser & PDDikti/MA/LPSE dorks
│   └── wilayah_data.py            # Complete 38 Provinces & 514 Kab/Kota dataset
│
├── sherlock/                      # Sherlock Engine (upstream: sherlock-project/sherlock)
├── maigret/                       # Maigret Engine (upstream: soxoj/maigret)
├── Osintgram/                     # Osintgram Engine (upstream: Datalux/Osintgram)
├── numint/                        # Numint Engine (upstream: whoamitang/numint)
├── snoop/                         # Snoop Engine (upstream: whoamitang/snoop)
├── holehe/                        # Holehe Engine (upstream: megadose/holehe)
└── GHunt/                         # GHunt Engine (upstream: mxrch/GHunt)
```

---

## 🔒 Security & Privacy Notice

- All personal credentials, Instagram cookies, SerpAPI keys (`.env`), search caches, private local databases (`data/*.db`), and generated dossier reports are strictly listed in [.gitignore](file:///.gitignore) and will **never** be committed or uploaded.
- Never commit your `credentials.ini`, `.env`, `instagrapi_session.json`, or local dataset files.

---

## ⚖️ Disclaimer

This toolkit is provided for educational, research, and legitimate cybersecurity auditing purposes only. Users are responsible for complying with all applicable local, national, and international laws, as well as the terms of service of any platforms queried. The developers and contributors assume no liability for misuse of this software.
