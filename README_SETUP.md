# OSINT Toolkit Setup (Windows 11 Pro)

This workspace contains 3 OSINT tools, completely configured with their own isolated Python virtual environments:

1. **[Sherlock](https://github.com/sherlock-project/sherlock)** (`sherlock/`) - Hunt down social media accounts by username across 400+ platforms.
2. **[Maigret](https://github.com/soxoj/maigret)** (`maigret/`) - Collect dossiers on a person by username across 5,900+ sites (CLI + Web UI).
3. **[Osintgram](https://github.com/Datalux/Osintgram)** (`Osintgram/`) - Instagram OSINT investigation tool with interactive Web UI (FastAPI).

---

## 🚀 Quick Launch (Double-Click Launchers)

In this root folder:

- **`menu.bat`** - **Master Interactive Menu**: Launch any tool, web UI, or Instagram login.
- **`sherlock.bat`** - Run Sherlock directly (prompts for username or accepts CLI flags).
- **`maigret.bat`** - Run Maigret directly (prompts for username or accepts CLI flags).
- **`osintgram.bat`** - Starts the Osintgram web server and opens `http://127.0.0.1:8000`.
- **`login_instagram.bat`** - One-time login to Instagram with Username & Password (for instagrapi).
- **`login_instagram_sessionid.bat`** - Alternative login via browser `sessionid` cookie (bypasses Instagram login blocks).

---

## 📸 Osintgram: Connecting `instagrapi`

Osintgram needs a backend to fetch Instagram data. Since you want to use **`instagrapi`** (free backend), you just need to authenticate once:

### Method A: Username & Password (with 2FA support)
1. Double-click **`login_instagram.bat`** (or choose Option `5` in `menu.bat`).
2. Enter your Instagram secondary account username and password.
3. If Instagram asks for a 2FA or SMS code, type it in the prompt.
4. Once completed, your session is saved to `Osintgram\config\instagrapi_session.json` and credentials are ready!
5. Now launch **`osintgram.bat`** and run your searches.

> ⚠️ *Tip: Always use a secondary / throwaway Instagram account for OSINT tools, never your primary personal account.*

### Method B: Browser Session ID (Recommended if Instagram blocks direct login)
If Instagram flags automated terminal login ("challenge required" or "out of date"):
1. Open [instagram.com](https://www.instagram.com) in Chrome/Edge/Firefox and log in.
2. Press `F12` (Developer Tools) -> Go to **Application** (Chrome/Edge) or **Storage** (Firefox).
3. Under **Cookies** -> `https://www.instagram.com`, find the cookie named **`sessionid`** and copy its value.
4. Double-click **`login_instagram_sessionid.bat`** (or choose Option `6` in `menu.bat`) and paste the `sessionid`.
5. That's it! The session is created instantly without triggering bot security blocks.

---

## 💻 Command Line / Terminal Usage

From PowerShell or Command Prompt in the toolkit directory:

### 1. Sherlock
```powershell
.\sherlock.bat <target_username>
.\sherlock.bat --site GitHub <target_username>
```

### 2. Maigret
```powershell
.\maigret.bat <target_username>
.\maigret.bat <target_username> -a          # Scan all 5,900+ sites
.\maigret.bat <target_username> --html      # Export HTML report
.\maigret.bat --web 5000                   # Launch Maigret Web UI (port 5000)
```

### 3. Osintgram Web UI
```powershell
.\osintgram.bat
# Opens http://127.0.0.1:8000 in your browser
```
