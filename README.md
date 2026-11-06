# 🔍 OSINT Toolkit for Windows 11

[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Multi--License-informational.svg)](LICENSE)
[![Engines](https://img.shields.io/badge/OSINT%20Engines-5%20Integrated-success)](#-included-engines--upstream-credits)
[![Status](https://img.shields.io/badge/Status-Turnkey%20Ready-brightgreen)](#)

A turnkey, pre-configured **Open-Source Intelligence (OSINT)** suite for Windows 11. 

This repository bundles and integrates **five industry-standard OSINT tools** with dedicated virtual environments, one-click Windows launchers, an interactive master terminal menu, and modern graphical Web dashboards.

---

## 📦 Included Engines & Upstream Credits

This suite integrates five phenomenal open-source projects. All core search capabilities, database definitions, and API clients belong to their respective original authors and maintainers. Full attribution is listed below:

| Engine | Upstream Repository | Author / Maintainers | License | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Sherlock** | [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) | Siddharth Dushantha & team | MIT | Fast username scanner checking 400+ social networks and web services. |
| **Maigret** | [soxoj/maigret](https://github.com/soxoj/maigret) | Soxoj | MIT | Deep username dossier profiling across 5,900+ sites with graph reports and built-in Web UI. |
| **Osintgram** | [Datalux/Osintgram](https://github.com/Datalux/Osintgram) | Giuseppe Criscione (Datalux) | GPLv3 | Interactive Instagram reconnaissance suite featuring an AI-assisted FastAPI Web Dashboard. |
| **Numint** | [whoamitang/numint](https://github.com/whoamitang/numint) | whoamitang & team | MIT | Professional phone number OSINT: carrier lookup, line type, spam risk score, registered accounts, and Web UI. |
| **Snoop** | [whoamitang/snoop](https://github.com/whoamitang/snoop) | whoamitang & team | MIT | Conservative, evidence-backed public profile audit, identity linking, document analysis, and case workspace. |

---

## ✨ Features

- **Isolated Virtual Environments (`.venv`)**: Each engine maintains its own isolated Python virtual environment, eliminating dependency version conflicts (e.g. `pydantic`, `aiohttp`, `fastapi`, `requests`).
- **Interactive Master Menu (`menu.bat`)**: Single control center to search usernames, inspect phone numbers, audit person footprints, start Web UIs, or authenticate Instagram.
- **One-Click Automated Setup (`setup.bat`)**: Sets up virtual environments and installs all required dependencies for all 5 tools in a single click.
- **Web Dashboards & CLI Support**:
  - **Sherlock**: High-speed command-line scanner with TXT/CSV/XLSX export.
  - **Maigret**: Rich terminal dossier generation + interactive graph Web UI on port `5000`.
  - **Osintgram**: Full visual Instagram dashboard on port `8000` with post grids, geolocation maps, posting heatmaps, and dossier export.
  - **Numint**: CLI scanner + visual phone intelligence Web dashboard on port `8080`.
  - **Snoop**: Evidence-backed investigation CLI + interactive web case workspace on port `8005`.
- **Seamless Instagram Authentication**:
  - Direct login with 2FA/SMS challenge handling (`login_instagram.bat`).
  - Browser `sessionid` authentication (`login_instagram_sessionid.bat`) to bypass aggressive bot detection challenges.

---

## 🚀 Quick Start (Windows)

### 1. Prerequisites
- **Windows 10 / 11 (64-bit)**
- **Python 3.11+** installed and added to `PATH` (download from [python.org](https://www.python.org/downloads/) or via Windows Terminal: `winget install Python.Python.3.13`).

### 2. Clone & Setup
```cmd
git clone https://github.com/aditzeb/osint-toolkit.git
cd osint-toolkit
```

Double-click **`setup.bat`** (or run `.\setup.bat` in Command Prompt / PowerShell).  
The script automatically provisions `.venv` for each tool, installs dependencies, initializes templates, and opens the master menu!

---

## 🎮 How to Use

### Master Control Center
Double-click **`menu.bat`** to open the interactive menu:
```text
============================================================
                     OSINT TOOLKIT
    Sherlock | Maigret | Osintgram | Numint | Snoop
============================================================

 --- USERNAME & SOCIAL OSINT ---
 [1] Sherlock       - Scan username across 400+ platforms (CLI)
 [2] Maigret        - Scan username dossier across 5,900+ sites (CLI)
 [3] Maigret Web    - Launch Maigret Web Graph UI (Port 5000)

 --- INSTAGRAM RECONNAISSANCE ---
 [4] Osintgram Web  - Launch Osintgram Web Dashboard (Port 8000)
 [5] Insta Login    - Authenticate Instagram (Username/Pass + 2FA)
 [6] Insta Session  - Authenticate Instagram (Browser Session ID)

 --- PHONE & PERSONA INTELLIGENCE ---
 [7] Numint         - Phone Number Intelligence Profile (CLI)
 [8] Numint Web     - Launch Numint Web Dashboard (Port 8080)
 [9] Snoop          - Person Footprint & Evidence Audit (CLI)
 [10] Snoop Web     - Launch Snoop Web Workspace (Port 8005)

 --- SYSTEM & TOOLS ---
 [11] OSINT Terminal - Command Prompt with all 5 tool environments
 [0]  Exit
============================================================
```

---

### Command-Line Usage

You can also run any tool directly from PowerShell or Command Prompt:

#### 1. Sherlock (Usernames across 400+ platforms)
```powershell
.\sherlock.bat target_username
.\sherlock.bat --site GitHub target_username
.\sherlock.bat --xlsx --csv target_username
```

#### 2. Maigret (Dossier profiler across 5,900+ sites)
```powershell
.\maigret.bat target_username
.\maigret.bat target_username -a          # Scan all 5,900+ sites
.\maigret.bat target_username --html      # Export HTML report
.\maigret.bat --web 5000                   # Launch Web UI (port 5000)
```

#### 3. Osintgram (Instagram Intelligence)
```powershell
.\osintgram.bat
# Automatically opens http://127.0.0.1:8000 in your browser
```

#### 4. Numint (Phone Number OSINT)
```powershell
# Scan any international phone number:
.\numint.bat +14155550123
.\numint.bat +628123456789

# Check configured data and AI providers:
.\numint.bat providers

# Launch Numint Web Dashboard:
.\numint_web.bat
# Automatically opens http://127.0.0.1:8080 in your browser
```

#### 5. Snoop (Persona Footprint & Case Investigation)
```powershell
# Investigate a target name or handle:
.\snoop.bat "Target Name"
.\snoop.bat "Target Name" --mode deep

# Diagnostics and provider readiness:
.\snoop.bat doctor

# Launch Snoop Web Workspace:
.\snoop_web.bat
# Automatically opens http://127.0.0.1:8005 in your browser
```

---

## 📸 Osintgram: Instagram Setup (`instagrapi`)

Osintgram uses Instagram data backends. To use the built-in free `instagrapi` backend, authenticate once:

> ⚠️ **Important Security Tip**: Always use a secondary / throwaway Instagram account for OSINT research. Never use your personal primary account.

### Method 1: Browser `sessionid` (Recommended)
Instagram often flags automated logins from terminal scripts. Using your existing browser session bypasses this:
1. Log in to [instagram.com](https://www.instagram.com) in Chrome, Edge, or Firefox.
2. Press **`F12`** $\rightarrow$ go to **Application** (Chrome/Edge) or **Storage** (Firefox) $\rightarrow$ **Cookies** $\rightarrow$ `https://www.instagram.com`.
3. Locate the cookie named **`sessionid`** and copy its value.
4. Double-click **`login_instagram_sessionid.bat`** (or option `6` in `menu.bat`), paste the `sessionid`, and press Enter.

### Method 2: Direct Username & Password
1. Double-click **`login_instagram.bat`** (or option `5` in `menu.bat`).
2. Enter your secondary Instagram username and password.
3. If Instagram sends a 2FA or SMS verification challenge, enter the code when prompted.

---

## 📁 Repository Structure

```text
OSINT-Toolkit/
├── menu.bat                       # Master interactive CLI menu (all 5 engines)
├── setup.bat                      # 1-click automated dependency installer
├── sherlock.bat                   # Sherlock launcher
├── maigret.bat                    # Maigret launcher
├── osintgram.bat                  # Osintgram Web server launcher
├── numint.bat                     # Numint Phone OSINT launcher
├── numint_web.bat                 # Numint Web dashboard launcher
├── snoop.bat                      # Snoop Persona OSINT launcher
├── snoop_web.bat                  # Snoop Web workspace launcher
├── login_instagram.bat            # Instagrapi CLI login helper
├── login_instagram_sessionid.bat  # Instagrapi sessionid login helper
├── .gitignore                     # Strict exclusion of sessions, credentials & caches
├── README.md                      # Documentation & Upstream Credits
│
├── sherlock/                      # Sherlock Engine (upstream: sherlock-project/sherlock)
│   ├── .venv/                     # Dedicated virtual environment
│   └── sherlock_project/          # Source code
│
├── maigret/                       # Maigret Engine (upstream: soxoj/maigret)
│   ├── .venv/                     # Dedicated virtual environment
│   └── maigret/                   # Source code
│
├── Osintgram/                     # Osintgram Engine (upstream: Datalux/Osintgram)
│   ├── .venv/                     # Dedicated virtual environment
│   ├── config/                    # Config directory (credentials.ini.example)
│   ├── scripts/                   # Instagrapi login helpers
│   └── src/                       # FastAPI web server and backend logic
│
├── numint/                        # Numint Engine (upstream: whoamitang/numint)
│   ├── .venv/                     # Dedicated virtual environment
│   └── src/numint/                # Phone scanning logic, API clients & Web UI
│
└── snoop/                         # Snoop Engine (upstream: whoamitang/snoop)
    ├── .venv/                     # Dedicated virtual environment
    └── snoop/                     # Profile investigation engine & case workspace
```

---

## 🔒 Security & Privacy Notice

- All personal credentials, Instagram cookies, search caches, and generated dossier reports are strictly listed in [.gitignore](file:///.gitignore) and will **never** be committed or uploaded.
- Never commit your `credentials.ini`, `.env`, or `instagrapi_session.json` files.

---

## ⚖️ Disclaimer

This toolkit is provided for educational, research, and legitimate cybersecurity auditing purposes only. Users are responsible for complying with all applicable local, national, and international laws, as well as the terms of service of any platforms queried. The developers and contributors assume no liability for misuse of this software.
