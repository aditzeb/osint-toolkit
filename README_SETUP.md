# OSINT Toolkit Setup (Windows 11 Pro)

This workspace contains 5 OSINT tools, completely configured with their own isolated Python virtual environments:

1. **[Sherlock](https://github.com/sherlock-project/sherlock)** (`sherlock/`) - Hunt down social media accounts by username across 400+ platforms.
2. **[Maigret](https://github.com/soxoj/maigret)** (`maigret/`) - Collect dossiers on a person by username across 5,900+ sites (CLI + Web UI).
3. **[Osintgram](https://github.com/Datalux/Osintgram)** (`Osintgram/`) - Instagram OSINT investigation tool with interactive Web UI (FastAPI).
4. **[Numint](https://github.com/whoamitang/numint)** (`numint/`) - Phone number intelligence profiling, carrier inspection, spam score, and Web UI.
5. **[Snoop](https://github.com/whoamitang/snoop)** (`snoop/`) - Evidence-backed public persona and profile audit, identity linking, and browser case workspace.

---

## 🚀 Quick Launch (Double-Click Launchers)

In this root folder:

- **`menu.bat`** - **Master Interactive Menu**: Launch any tool, web UI, or Instagram login.
- **`setup.bat`** - **1-Click Automated Setup**: Provisions all 5 virtual environments and installs all dependencies.
- **`sherlock.bat`** - Run Sherlock directly (prompts for username or accepts CLI flags).
- **`maigret.bat`** - Run Maigret directly (prompts for username or accepts CLI flags).
- **`osintgram.bat`** - Starts the Osintgram web server and opens `http://127.0.0.1:8000`.
- **`numint.bat`** - Run Numint phone scanner directly (prompts for phone number or accepts flags).
- **`numint_web.bat`** - Starts Numint web dashboard on `http://127.0.0.1:8080`.
- **`snoop.bat`** - Run Snoop persona investigator directly.
- **`snoop_web.bat`** - Starts Snoop web workspace on `http://127.0.0.1:8005`.
- **`login_instagram.bat`** - One-time login to Instagram with Username & Password (for instagrapi).
- **`login_instagram_sessionid.bat`** - Alternative login via browser `sessionid` cookie (bypasses Instagram login blocks).

---

## 📸 Osintgram: Connecting `instagrapi`

Osintgram needs a backend to fetch Instagram data. Since you want to use **`instagrapi`** (free backend), authenticate once:

### Method A: Browser Session ID (Recommended)
1. Log in to [instagram.com](https://www.instagram.com) in your browser.
2. Press `F12` -> **Application** (Chrome/Edge) or **Storage** (Firefox) -> **Cookies** -> `https://www.instagram.com`.
3. Copy the value of the `sessionid` cookie.
4. Double-click `login_instagram_sessionid.bat` (or option 6 in `menu.bat`) and paste it.

### Method B: Username & Password
1. Double-click `login_instagram.bat` (or option 5 in `menu.bat`).
2. Enter username, password, and 2FA code if prompted.

---

## 💻 Command Line / Terminal Usage

From PowerShell or Command Prompt in the toolkit directory:

```powershell
# Sherlock
.\sherlock.bat <target_username>

# Maigret
.\maigret.bat <target_username> -a
.\maigret.bat --web 5000

# Osintgram Web UI
.\osintgram.bat

# Numint Phone OSINT
.\numint.bat +14155550123
.\numint_web.bat

# Snoop Persona Audit
.\snoop.bat "Target Name"
.\snoop_web.bat
```
