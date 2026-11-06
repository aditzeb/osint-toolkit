# 🔍 OSINT Toolkit for Windows 11

[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Multi--License-informational.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Turnkey%20Ready-brightgreen)](#)

A turnkey, pre-configured **Open-Source Intelligence (OSINT)** reconnaissance suite for Windows 11. 

This repository bundles and integrates three industry-standard OSINT tools with dedicated virtual environments, one-click Windows launchers, interactive terminal menus, and modern Web interfaces.

---

## 📦 Included Engines & Upstream Credits

This suite integrates three phenomenal open-source projects. All core search capabilities, database definitions, and API clients belong to their respective original authors and maintainers. Full attribution is listed below:

| Engine | Upstream Repository | Author / Maintainers | License | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Sherlock** | [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) | Siddharth Dushantha & team | MIT | Fast username scanner checking 400+ social networks and web services. |
| **Maigret** | [soxoj/maigret](https://github.com/soxoj/maigret) | Soxoj | MIT | Deep username dossier profiling across 5,900+ sites with graph reports and built-in Web UI. |
| **Osintgram** | [Datalux/Osintgram](https://github.com/Datalux/Osintgram) | Giuseppe Criscione (Datalux) | GPLv3 | Interactive Instagram reconnaissance suite featuring an AI-assisted FastAPI Web Dashboard. |

---

## ✨ Features

- **Isolated Virtual Environments (`.venv`)**: Each engine maintains its own isolated Python virtual environment, eliminating dependency version conflicts (e.g. `requests`, `aiohttp`, `pydantic`).
- **Interactive Master Menu (`menu.bat`)**: Single control center to search with Sherlock, profile with Maigret, start Web UIs, or authenticate Instagram.
- **One-Click Automated Setup (`setup.bat`)**: Sets up virtual environments and installs all required dependencies in a single run.
- **Web UI & CLI Support**:
  - **Sherlock**: High-speed command-line scanner with TXT/CSV/XLSX export.
  - **Maigret**: Rich terminal dossier generation + interactive graph Web UI on port `5000`.
  - **Osintgram**: Full visual dashboard on port `8000` with post grids, geolocation maps, posting heatmaps, and dossier export.
- **Seamless Instagram Authentication**:
  - Direct login with 2FA/SMS challenge handling (`login_instagram.bat`).
  - Browser `sessionid` authentication (`login_instagram_sessionid.bat`) to bypass aggressive bot detection challenges.

---

## 🚀 Quick Start (Windows)

### 1. Prerequisites
- **Windows 10 / 11 (64-bit)**
- **Python 3.10+** installed and added to `PATH` (download from [python.org](https://www.python.org/downloads/) or via Windows Terminal: `winget install Python.Python.3.13`).

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
            Sherlock | Maigret | Osintgram
============================================================

 [1] Sherlock  - Scan username across 400+ platforms (CLI)
 [2] Maigret   - Scan username across 5,900+ sites (CLI)
 [3] Maigret Web UI  - Launch Maigret Web Interface
 [4] Osintgram Web UI - Launch Osintgram Web Interface

 -- Osintgram Instagram Authentication (instagrapi) --
 [5] Login Instagram with Username/Password (+ 2FA)
 [6] Login Instagram with Browser Session ID (Recommended)

 [7] Open OSINT Command Prompt (Environment Ready)
 [0] Exit
============================================================
```

---

### Command-Line Usage

You can also run any tool directly from PowerShell or Command Prompt:

#### 1. Sherlock
```powershell
# Interactive prompt:
.\sherlock.bat

# Direct target scan:
.\sherlock.bat target_username

# Specific site filter:
.\sherlock.bat --site GitHub target_username

# Export modern Excel (.xlsx) and CSV:
.\sherlock.bat --xlsx --csv target_username
```

#### 2. Maigret
```powershell
# Interactive prompt:
.\maigret.bat

# Standard search (top 500 Alexa sites):
.\maigret.bat target_username

# Deep search across all 5,900+ sites:
.\maigret.bat target_username -a

# Generate standalone HTML dossier report:
.\maigret.bat target_username --html

# Launch Maigret Web UI on port 5000:
.\maigret.bat --web 5000
# Then open http://127.0.0.1:5000
```

#### 3. Osintgram Web Dashboard
```powershell
# Start FastAPI Web Server:
.\osintgram.bat
# Automatically opens http://127.0.0.1:8000 in your browser
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
├── menu.bat                       # Master interactive CLI menu
├── setup.bat                      # 1-click automated dependency installer
├── sherlock.bat                   # Sherlock Windows launcher
├── maigret.bat                    # Maigret Windows launcher
├── osintgram.bat                  # Osintgram Web server launcher
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
└── Osintgram/                     # Osintgram Engine (upstream: Datalux/Osintgram)
    ├── .venv/                     # Dedicated virtual environment
    ├── config/                    # Config directory (credentials.ini.example)
    ├── scripts/                   # Instagrapi login helpers
    └── src/                       # FastAPI web server and backend logic
```

---

## 🔒 Security & Privacy Notice

- All personal credentials, Instagram cookies, search caches, and generated dossier reports are strictly listed in [.gitignore](file:///.gitignore) and will **never** be committed or uploaded.
- Never commit your `credentials.ini` or `instagrapi_session.json` files.

---

## ⚖️ Disclaimer

This toolkit is provided for educational, research, and legitimate cybersecurity auditing purposes only. Users are responsible for complying with all applicable local, national, and international laws, as well as the terms of service of any platforms queried. The developers and contributors assume no liability for misuse of this software.
