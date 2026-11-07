# 🔍 OSINT Toolkit for Windows 11 (Global + Indonesia Edition)

[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Multi--License-informational.svg)](LICENSE)
[![Engines](https://img.shields.io/badge/OSINT%20Engines-8%20Integrated-success)](#-included-engines--upstream-credits)
[![Status](https://img.shields.io/badge/Status-Turnkey%20Ready-brightgreen)](#)

A turnkey, pre-configured **Open-Source Intelligence (OSINT)** suite for Windows 11. 

This repository bundles and integrates **eight OSINT engines**—combining seven industry-standard global reconnaissance tools with a built-in **Indonesia OSINT Intelligence Suite (`indo_osint`)**—complete with isolated virtual environments, one-click Windows launchers, an interactive master terminal menu, and modern graphical Web dashboards.

---

## 📦 Included Engines & Upstream Credits

This suite integrates seven open-source projects alongside a custom Indonesian regional intelligence package. All core search capabilities, database definitions, and API clients belong to their respective original authors and maintainers. Full attribution is listed below:

| Engine | Upstream Repository | Author / Maintainers | License | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Sherlock** | [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) | Siddharth Dushantha & team | MIT | Fast username scanner checking 400+ social networks and web services. |
| **Maigret** | [soxoj/maigret](https://github.com/soxoj/maigret) | Soxoj | MIT | Deep username dossier profiling across 5,900+ sites with graph reports and built-in Web UI. |
| **Osintgram** | [Datalux/Osintgram](https://github.com/Datalux/Osintgram) | Giuseppe Criscione (Datalux) | GPLv3 | Interactive Instagram reconnaissance suite featuring an AI-assisted FastAPI Web Dashboard. |
| **Numint** | [whoamitang/numint](https://github.com/whoamitang/numint) | whoamitang & team | MIT | Professional phone number OSINT: carrier lookup, line type, spam risk score, registered accounts, and Web UI. |
| **Snoop** | [whoamitang/snoop](https://github.com/whoamitang/snoop) | whoamitang & team | MIT | Conservative, evidence-backed public profile audit, identity linking, document analysis, and case workspace. |
| **Holehe** | [megadose/holehe](https://github.com/megadose/holehe) | Palenath (megadose) | GPLv3 | Checks if an email address is registered across 120+ sites (Twitter, Instagram, Spotify, Adobe, etc.) without alerting the target. |
| **GHunt** | [mxrch/GHunt](https://github.com/mxrch/GHunt) | mxrch | AGPL-3.0 | Offensive Google / Gmail framework extracting GAIA ID, Maps reviews, Calendar, Photos, and Drive artifacts. |
| **Indo OSINT** | `indo_osint/` (Built-in) | OSINT Toolkit Contributors | MIT | Indonesian Regional Intelligence: 16-digit NIK KTP decoder, 18-digit NIP ASN parser, Telco & E-Wallet VA generator, Plat Nomor TNKB decoder, and PDDikti / Mahkamah Agung / LPSE dorks. |

---

## ✨ Features

- **All-in-One Master Navigator (`app.py` & `run.bat` / `menu.bat`)**: Unified interactive control center with rich hierarchical menus, target-oriented guided workflows, dual-engine sequential scans, web dashboard manager, evidence locker, and diagnostic self-healing.
- **Isolated Virtual Environments (`.venv`)**: Each external engine maintains its own isolated Python virtual environment, eliminating dependency version conflicts (e.g. `pydantic`, `aiohttp`, `fastapi`, `httpx`, `pillow`).
- **Interactive Master Menu (`menu.bat`)**: Single control center with 14 quick actions to scan usernames, check emails, inspect phone numbers, audit person footprints, run Indonesian regional intelligence, or launch Web UIs.
- **One-Click Automated Setup (`setup.bat`)**: Sets up virtual environments and installs all required dependencies in a single click.
- **Indonesia OSINT Intelligence (`indo_osint`)**:
  - **NIK KTP 16-Digit Decoder**: Extracts Province (38 provinces), Kabupaten/Kota (514 regencies/cities), Kecamatan (live Kemendagri Dukcapil lookup), Gender, Birthdate, Age, Javanese Weton/Pasaran, Zodiac, Generation, and sequence number.
  - **NIP ASN / PNS 18-Digit Decoder**: Extracts Birthdate, CPNS Appointment Year/Month (TMT), years of service, BUP retirement year, and gender.
  - **Indonesian Phone & E-Wallet VA Generator**: Identifies Indonesian cellular operators (Telkomsel, Indosat, XL, Axis, Tri, Smartfren) and 80+ PSTN landline area codes, generates Virtual Account codes for **DANA, OVO, GoPay, ShopeePay, and LinkAja**, and builds Indonesian fraud/marketplace dorks.
  - **Indonesian License Plate (Plat Nomor / TNKB) Decoder**: Maps all regional codes (`A`–`PY`), decodes Jadetabek (`B`) city sub-codes and vehicle classifications, and links to regional E-Samsat portals.
  - **Indonesian Public Registry Dorks**: Generates targeted queries for **PDDikti** (students/lecturers), **Putusan Mahkamah Agung** (court verdicts), **SIPP Pengadilan**, **LPSE** government procurement, and **AHU Kemenkumham** company records.
- **Web Dashboards & CLI Support**:
  - **Maigret Web UI** on port `5000`
  - **Osintgram Web Dashboard** on port `8000`
  - **Numint Web Dashboard** on port `8080`
  - **Snoop Web Workspace** on port `8005`

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

### 🌟 All-in-One Master Navigator (`run.bat` / `menu.bat` / `app.py`)
Simply double-click **`run.bat`** (or **`menu.bat`**) to launch the interactive Master Navigator. 

The application automatically launches the rich, color-coded **`app.py`** console interface (or seamlessly falls back to pure Batch mode if run with `--batch` or in environments without Python):

```text
============================================================================
   🔍  OSINT TOOLKIT - ALL-IN-ONE MASTER CONTROL CENTER (WINDOWS 11)   
   Sherlock | Maigret | Osintgram | Numint | Snoop | Holehe | GHunt | ID
============================================================================
 📍 Navigation: Main Navigation
----------------------------------------------------------------------------
Select an operation mode to begin:

 [1] 🎯 TARGET INVESTIGATION       (Guided search: Username, Email, Phone, NIK, etc.)
 [2] ⚙️  INDIVIDUAL WORKSPACES      (Direct CLI for Sherlock, Maigret, Holehe, etc.)
 [3] 🌐 WEB DASHBOARDS HUB         (One-Click Launch: Ports 5000, 8000, 8080, 8005)
 [4] 📁 EVIDENCE & REPORTS LOCKER  (View generated HTML/CSV/XLSX intelligence)
 [5] 🩺 HEALTH & SYSTEM DIAGNOSTICS(Verify all 8 venvs, run setup, or open shell)

 [0] 🚪 Exit Application
----------------------------------------------------------------------------
```

### 🧭 Hierarchical Navigation Features

1. **🎯 Target Investigation (Multi-Engine Orchestration)**:
   - **Username OSINT**: Run Sherlock (400+ platforms), Maigret (5,900+ sites), or a **Dual-Engine Scan** executing both in sequence with reports saved to `reports/`.
   - **Email Intelligence**: Run Holehe (120+ platforms) and GHunt (Google Account, Gaia ID, Maps reviews) individually or via **Dual Email Recon**.
   - **Phone Intelligence**: Numint global profile + Indonesian Telco & E-Wallet VA generator (DANA, OVO, GoPay, ShopeePay, LinkAja).
   - **Indonesia Regional Intelligence**: 16-digit NIK KTP, 18-digit NIP ASN, Plat Nomor TNKB, and PDDikti/Mahkamah Agung/LPSE public registry dorks.
   - **Instagram Reconnaissance**: Launch Osintgram Web UI, login via credentials, or authenticate via browser `sessionid`.
   - **Persona Footprint Audit**: Run Snoop standard or deep evidence-backed investigation.

2. **🌐 Web Dashboards Hub (One-Click Launch & Monitor)**:
   - Live port inspection checks if services are already running on ports `5000`, `8000`, `8080`, and `8005`.
   - Launch individual dashboards or trigger **Option [5]** to launch all four web UIs simultaneously and open them in your browser!

3. **📁 Evidence Locker & Reports Viewer**:
   - Centralizes and catalogs all exported files (`.html`, `.csv`, `.xlsx`, `.pdf`, `.json`) in `reports/`.
   - Open reports immediately in your default browser or spreadsheet viewer.
   - One-click button to open the `reports/` folder in Windows File Explorer.

4. **🩺 System Diagnostics & Developer Shell**:
   - Live status check for all 8 virtual environments and dependencies.
   - One-click trigger for `setup.bat` to provision or repair missing environments.
   - Spawns an **OSINT Developer Terminal** with all eight `.venv\Scripts` loaded into `PATH`.

---

### Command-Line Usage

You can run any tool directly from PowerShell or Command Prompt:

#### 1. Sherlock (Usernames across 400+ platforms)
```powershell
.\sherlock.bat target_username
.\sherlock.bat --xlsx --csv target_username
```

#### 2. Maigret (Dossier profiler across 5,900+ sites)
```powershell
.\maigret.bat target_username
.\maigret.bat target_username -a          # Scan all 5,900+ sites
.\maigret.bat --web 5000                   # Launch Web UI (port 5000)
```

#### 3. Osintgram (Instagram Intelligence)
```powershell
.\osintgram.bat
# Automatically opens http://127.0.0.1:8000 in your browser
```

#### 4. Numint (Phone Number OSINT)
```powershell
.\numint.bat +6281234567890
.\numint.bat providers
.\numint_web.bat                          # Opens http://127.0.0.1:8080
```

#### 5. Snoop (Persona Footprint & Case Investigation)
```powershell
.\snoop.bat "Target Name"
.\snoop.bat "Target Name" --mode deep
.\snoop_web.bat                           # Opens http://127.0.0.1:8005
```

#### 6. Holehe (Email OSINT across 120+ platforms)
```powershell
.\holehe.bat target@example.com
.\holehe.bat --only-used target@example.com
```

#### 7. GHunt (Google / Gmail OSINT)
```powershell
.\ghunt.bat login                         # One-time Google cookie authentication
.\ghunt.bat email target@gmail.com
.\ghunt.bat gaia <GAIA_ID>
```

#### 8. Indonesia OSINT Suite (`indo_osint.bat`)
```powershell
# Interactive Menu:
.\indo_osint.bat

# Direct CLI Flags:
.\indo_osint.bat --nik 3174011708950001
.\indo_osint.bat --nip 199008172019031005
.\indo_osint.bat --phone 081234567890
.\indo_osint.bat --plate "B 1234 KAA"
.\indo_osint.bat --dorks "Budi Santoso" --univ "Universitas Indonesia"
```

---

## 📸 Osintgram: Instagram Setup (`instagrapi`)

Osintgram uses Instagram data backends. To use the built-in free `instagrapi` backend, authenticate once:

> ⚠️ **Important Security Tip**: Always use a secondary / throwaway Instagram account for OSINT research. Never use your personal primary account.

1. Log in to [instagram.com](https://www.instagram.com) in Chrome, Edge, or Firefox.
2. Press **`F12`** $\rightarrow$ go to **Application** (Chrome/Edge) or **Storage** (Firefox) $\rightarrow$ **Cookies** $\rightarrow$ `https://www.instagram.com`.
3. Locate the cookie named **`sessionid`** and copy its value.
4. Double-click **`login_instagram_sessionid.bat`** (or option `6` in `menu.bat`), paste the `sessionid`, and press Enter.

---

## 📁 Repository Structure

```text
OSINT-Toolkit/
├── run.bat                        # 1-Click All-in-One Master Launcher
├── menu.bat                       # Master CLI & Batch menu (launches app.py or fallback)
├── app.py                         # All-in-One Interactive Navigator (guided workflows & hub)
├── setup.bat                      # 1-click automated dependency installer
├── reports/                       # Centralized evidence locker for generated dossiers
├── sherlock.bat                   # Sherlock launcher
├── maigret.bat                    # Maigret launcher
├── osintgram.bat                  # Osintgram Web server launcher
├── numint.bat                     # Numint Phone OSINT launcher
├── numint_web.bat                 # Numint Web dashboard launcher
├── snoop.bat                      # Snoop Persona OSINT launcher
├── snoop_web.bat                  # Snoop Web workspace launcher
├── holehe.bat                     # Holehe Email OSINT launcher
├── ghunt.bat                      # GHunt Google OSINT launcher
├── indo_osint.bat                 # Indonesia OSINT Suite launcher
├── login_instagram.bat            # Instagrapi CLI login helper
├── login_instagram_sessionid.bat  # Instagrapi sessionid login helper
├── .gitignore                     # Strict exclusion of sessions, credentials & caches
├── README.md                      # Documentation & Upstream Credits
│
├── indo_osint/                    # Indonesia OSINT Intelligence Suite
│   ├── cli.py                     # Interactive CLI & command-line flags
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

- All personal credentials, Instagram cookies, SerpAPI keys (`.env`), search caches, and generated dossier reports are strictly listed in [.gitignore](file:///.gitignore) and will **never** be committed or uploaded.
- Never commit your `credentials.ini`, `.env`, or `instagrapi_session.json` files.

---

## ⚖️ Disclaimer

This toolkit is provided for educational, research, and legitimate cybersecurity auditing purposes only. Users are responsible for complying with all applicable local, national, and international laws, as well as the terms of service of any platforms queried. The developers and contributors assume no liability for misuse of this software.
