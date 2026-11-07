# OSINT Toolkit Setup (Windows 11 Pro)

This workspace contains 8 OSINT engines, completely configured with isolated Python virtual environments:

1. **[Sherlock](https://github.com/sherlock-project/sherlock)** (`sherlock/`) - Hunt down social media accounts by username across 400+ platforms.
2. **[Maigret](https://github.com/soxoj/maigret)** (`maigret/`) - Collect dossiers on a person by username across 5,900+ sites (CLI + Web UI).
3. **[Osintgram](https://github.com/Datalux/Osintgram)** (`Osintgram/`) - Instagram OSINT investigation tool with interactive Web UI (FastAPI).
4. **[Numint](https://github.com/whoamitang/numint)** (`numint/`) - Phone number intelligence profiling, carrier inspection, spam score, and Web UI.
5. **[Snoop](https://github.com/whoamitang/snoop)** (`snoop/`) - Evidence-backed public persona and profile audit, identity linking, and browser case workspace.
6. **[Holehe](https://github.com/megadose/holehe)** (`holehe/`) - Check registered accounts by email across 120+ platforms without alerting the target.
7. **[GHunt](https://github.com/mxrch/GHunt)** (`GHunt/`) - Google / Gmail account OSINT framework.
8. **Indonesia OSINT Suite** (`indo_osint/`) - 16-digit NIK KTP decoder, 18-digit NIP ASN parser, Telco & E-Wallet VA generator, Plat Nomor TNKB decoder, and PDDikti / Mahkamah Agung / LPSE dork generator.

---

## 🚀 Quick Launch (Double-Click Launchers)

In this root folder:

- **`menu.bat`** - **Master Interactive Menu**: Launch any of the 8 engines, web UIs, or login helpers.
- **`setup.bat`** - **1-Click Automated Setup**: Provisions all virtual environments and installs all dependencies.
- **`sherlock.bat`** - Run Sherlock directly (prompts for username or accepts CLI flags).
- **`maigret.bat`** - Run Maigret directly (prompts for username or accepts CLI flags).
- **`osintgram.bat`** - Starts the Osintgram web server and opens `http://127.0.0.1:8000`.
- **`numint.bat`** - Run Numint phone scanner directly (prompts for phone number or accepts flags).
- **`numint_web.bat`** - Starts Numint web dashboard on `http://127.0.0.1:8080`.
- **`snoop.bat`** - Run Snoop persona investigator directly.
- **`snoop_web.bat`** - Starts Snoop web workspace on `http://127.0.0.1:8005`.
- **`holehe.bat`** - Check email registration across 120+ sites.
- **`ghunt.bat`** - Run GHunt Google/Gmail OSINT.
- **`indo_osint.bat`** - Launch the Indonesia OSINT Intelligence Suite (interactive menu or CLI flags).
- **`login_instagram.bat`** - One-time login to Instagram with Username & Password (for instagrapi).
- **`login_instagram_sessionid.bat`** - Alternative login via browser `sessionid` cookie (bypasses Instagram login blocks).
