#!/usr/bin/env python3
"""
================================================================================
              OSINT TOOLKIT - ALL-IN-ONE MASTER CONTROL CENTER (v2.1)
         Sherlock | Maigret | Osintgram | Numint | Snoop | Holehe | GHunt
                  + INDONESIA OSINT & DATA BOCOR INTELLIGENCE
================================================================================
Author: OSINT Toolkit Maintainers
License: MIT / Multi-License
Platform: Windows 11 / 10 / Cross-Platform
"""

import os
import sys
import subprocess
import webbrowser
import socket
import time
import shutil
from pathlib import Path
from datetime import datetime

# Enable ANSI escape sequences on Windows
if sys.platform == "win32":
    os.system("")

# ANSI Color Codes
C_RESET   = "\033[0m"
C_BOLD    = "\033[1m"
C_DIM     = "\033[2m"
C_CYAN    = "\033[96m"
C_BLUE    = "\033[94m"
C_GREEN   = "\033[92m"
C_YELLOW  = "\033[93m"
C_RED     = "\033[91m"
C_MAGENTA = "\033[95m"
C_WHITE   = "\033[97m"

ROOT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = ROOT_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ENGINES = {
    "sherlock": {
        "name": "Sherlock",
        "desc": "Scan username across 400+ platforms",
        "exe": ROOT_DIR / "sherlock" / ".venv" / "Scripts" / "sherlock.exe",
        "dir": ROOT_DIR / "sherlock",
    },
    "maigret": {
        "name": "Maigret",
        "desc": "Collect dossier across 5,900+ sites",
        "exe": ROOT_DIR / "maigret" / ".venv" / "Scripts" / "maigret.exe",
        "dir": ROOT_DIR / "maigret",
    },
    "holehe": {
        "name": "Holehe",
        "desc": "Check email registrations on 120+ sites",
        "exe": ROOT_DIR / "holehe" / ".venv" / "Scripts" / "holehe.exe",
        "dir": ROOT_DIR / "holehe",
    },
    "ghunt": {
        "name": "GHunt",
        "desc": "Google / Gmail account intelligence (Gaia ID, Maps)",
        "exe": ROOT_DIR / "GHunt" / ".venv" / "Scripts" / "ghunt.exe",
        "dir": ROOT_DIR / "GHunt",
    },
    "numint": {
        "name": "Numint",
        "desc": "Phone intelligence profile, carrier & risk score",
        "exe": ROOT_DIR / "numint" / ".venv" / "Scripts" / "numint.exe",
        "dir": ROOT_DIR / "numint",
    },
    "snoop": {
        "name": "Snoop",
        "desc": "Persona footprint audit & evidence linking",
        "exe": ROOT_DIR / "snoop" / ".venv" / "Scripts" / "snoop.exe",
        "dir": ROOT_DIR / "snoop",
    },
    "osintgram": {
        "name": "Osintgram",
        "desc": "Instagram reconnaissance suite & Web Dashboard",
        "uvicorn": ROOT_DIR / "Osintgram" / ".venv" / "Scripts" / "uvicorn.exe",
        "python": ROOT_DIR / "Osintgram" / ".venv" / "Scripts" / "python.exe",
        "dir": ROOT_DIR / "Osintgram",
    },
    "indo_osint": {
        "name": "Indo OSINT",
        "desc": "Indonesian Regional Intelligence (NIK, NIP, Phone, Plat, Dorks, Data Bocor, Local DB)",
        "cli": ROOT_DIR / "indo_osint" / "cli.py",
        "dir": ROOT_DIR / "indo_osint",
    },
}

WEB_SERVICES = {
    "maigret": {
        "name": "Maigret Web UI",
        "port": 5000,
        "url": "http://127.0.0.1:5000",
        "cmd": [str(ENGINES["maigret"]["exe"]), "--web", "5000"],
        "cwd": ROOT_DIR,
    },
    "osintgram": {
        "name": "Osintgram Web Dashboard",
        "port": 8000,
        "url": "http://127.0.0.1:8000",
        "cmd": [str(ENGINES["osintgram"]["uvicorn"]), "src.web.app:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": ENGINES["osintgram"]["dir"],
    },
    "numint": {
        "name": "Numint Web Dashboard",
        "port": 8080,
        "url": "http://127.0.0.1:8080",
        "cmd": [str(ENGINES["numint"]["exe"]), "web", "--port", "8080"],
        "cwd": ROOT_DIR,
    },
    "snoop": {
        "name": "Snoop Web Workspace",
        "port": 8005,
        "url": "http://127.0.0.1:8005",
        "cmd": [str(ENGINES["snoop"]["exe"]), "web", "--port", "8005"],
        "cwd": ROOT_DIR,
    },
}


def clear_screen():
    os.system("cls" if sys.platform == "win32" else "clear")


def print_banner(breadcrumbs="Home"):
    clear_screen()
    print(f"{C_CYAN}{C_BOLD}" + "=" * 76 + f"{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}   🔍  OSINT TOOLKIT - ALL-IN-ONE MASTER CONTROL CENTER (WINDOWS 11)   {C_RESET}")
    print(f"{C_DIM}   Sherlock | Maigret | Osintgram | Numint | Snoop | Holehe | GHunt | ID{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}" + "=" * 76 + f"{C_RESET}")
    print(f"{C_BLUE}{C_BOLD} 📍 Navigation:{C_RESET} {C_YELLOW}{breadcrumbs}{C_RESET}")
    print(f"{C_DIM}" + "-" * 76 + f"{C_RESET}")


def pause_prompt():
    print(f"\n{C_DIM}Press Enter to return to menu...{C_RESET}", end="")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass


def is_port_listening(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def check_engine_health(key: str) -> bool:
    engine = ENGINES.get(key)
    if not engine:
        return False
    if key == "indo_osint":
        return engine["cli"].exists()
    if key == "osintgram":
        return engine["uvicorn"].exists()
    return engine["exe"].exists()


def run_command_interactive(cmd_list, cwd=None):
    """Run an engine command with live output in the console."""
    print(f"{C_DIM}Executing: {' '.join(str(c) for c in cmd_list)}{C_RESET}\n")
    try:
        res = subprocess.run(cmd_list, cwd=str(cwd or ROOT_DIR))
        return res.returncode
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}[!] Execution interrupted by user.{C_RESET}")
        return 130
    except Exception as e:
        print(f"\n{C_RED}[ERROR] Failed to run command: {e}{C_RESET}")
        return 1


# ==============================================================================
# 1. GUIDED TARGET INVESTIGATION WORKFLOWS
# ==============================================================================

def workflow_username():
    while True:
        print_banner("Target Investigation > Username OSINT")
        print(f"{C_WHITE}{C_BOLD}Hunt down accounts across 6,000+ platforms worldwide:{C_RESET}\n")
        print(f" {C_GREEN}[1]{C_RESET} Fast Username Scan   (Sherlock - 400+ platforms)")
        print(f" {C_GREEN}[2]{C_RESET} Deep Dossier Scan    (Maigret - 5,900+ sites, top 500 fast mode)")
        print(f" {C_GREEN}[3]{C_RESET} All-Sites Dossier    (Maigret - comprehensive all 5,900+ sites)")
        print(f" {C_GREEN}[4]{C_RESET} 🚀 Dual-Engine Scan  (Runs Sherlock + Maigret in sequence)")
        print(f" {C_GREEN}[5]{C_RESET} Launch Maigret Web   (Interactive Web Graph UI on Port 5000)")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Previous Menu")
        print(f" {C_RED}[0]{C_RESET} Return to Main Menu")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            return "MAIN"

        if choice in ["1", "2", "3", "4"]:
            username = input(f"\n{C_WHITE}Enter target username to scan:{C_RESET} ").strip()
            if not username:
                print(f"{C_RED}[!] Username cannot be empty.{C_RESET}")
                time.sleep(1)
                continue

            # Verify virtual environments
            if choice in ["1", "4"] and not check_engine_health("sherlock"):
                print(f"{C_RED}[ERROR] Sherlock venv not found. Run Setup [Option 5] first.{C_RESET}")
                pause_prompt()
                continue
            if choice in ["2", "3", "4"] and not check_engine_health("maigret"):
                print(f"{C_RED}[ERROR] Maigret venv not found. Run Setup [Option 5] first.{C_RESET}")
                pause_prompt()
                continue

            clear_screen()

            if choice == "1":
                print(f"{C_GREEN}[+] Starting Sherlock scan for '{username}'...{C_RESET}")
                run_command_interactive([
                    str(ENGINES["sherlock"]["exe"]),
                    "--folderoutput", str(REPORTS_DIR),
                    "--csv", "--xlsx",
                    username
                ])
            elif choice == "2":
                print(f"{C_GREEN}[+] Starting Maigret fast dossier scan for '{username}'...{C_RESET}")
                run_command_interactive([
                    str(ENGINES["maigret"]["exe"]),
                    "--folderoutput", str(REPORTS_DIR),
                    "--html", "--pdf",
                    username
                ])
            elif choice == "3":
                print(f"{C_GREEN}[+] Starting Maigret full exhaustive scan (-a) for '{username}'...{C_RESET}")
                run_command_interactive([
                    str(ENGINES["maigret"]["exe"]),
                    "-a",
                    "--folderoutput", str(REPORTS_DIR),
                    "--html", "--pdf",
                    username
                ])
            elif choice == "4":
                print(f"{C_CYAN}{C_BOLD}=== STAGE 1/2: SHERLOCK SCAN (400+ SITES) ==={C_RESET}")
                run_command_interactive([
                    str(ENGINES["sherlock"]["exe"]),
                    "--folderoutput", str(REPORTS_DIR),
                    "--csv", "--xlsx",
                    username
                ])
                print(f"\n{C_CYAN}{C_BOLD}=== STAGE 2/2: MAIGRET DOSSIER SCAN ==={C_RESET}")
                run_command_interactive([
                    str(ENGINES["maigret"]["exe"]),
                    "--folderoutput", str(REPORTS_DIR),
                    "--html", "--pdf",
                    username
                ])
                print(f"\n{C_GREEN}[✓] Dual Username Reconnaissance Complete! Results saved to reports/{C_RESET}")

            pause_prompt()

        elif choice == "5":
            launch_web_service("maigret")
            pause_prompt()


def workflow_email():
    while True:
        print_banner("Target Investigation > Email Intelligence & Data Bocor")
        print(f"{C_WHITE}{C_BOLD}Investigate email addresses across 120+ platforms, breaches, stealers & Google:{C_RESET}\n")
        print(f" {C_GREEN}[1]{C_RESET} Holehe Scan           (Check registration across 120+ platforms)")
        print(f" {C_GREEN}[2]{C_RESET} Holehe Used Only      (Filter and display registered sites only)")
        print(f" {C_GREEN}[3]{C_RESET} GHunt Email OSINT     (Google Account, GAIA ID, Maps, Drive, Photos)")
        print(f" {C_GREEN}[4]{C_RESET} ⚠️ Data Bocor & Stealers(Live XposedOrNot breaches & Hudson Rock stealers)")
        print(f" {C_GREEN}[5]{C_RESET} 🚀 Triple Email Recon (Holehe + GHunt + Live Data Bocor Scan)")
        print(f" {C_GREEN}[6]{C_RESET} GHunt Login Wizard    (Authenticate Google cookies for GHunt)")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Previous Menu")
        print(f" {C_RED}[0]{C_RESET} Return to Main Menu")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            return "MAIN"

        if choice in ["1", "2", "3", "4", "5"]:
            target_email = input(f"\n{C_WHITE}Enter target email address:{C_RESET} ").strip()
            if not target_email or "@" not in target_email:
                print(f"{C_RED}[!] Please enter a valid email address.{C_RESET}")
                time.sleep(1)
                continue

            if choice in ["1", "2", "5"] and not check_engine_health("holehe"):
                print(f"{C_RED}[ERROR] Holehe venv not found. Run Setup [Option 5] first.{C_RESET}")
                pause_prompt()
                continue
            if choice in ["3", "5"] and not check_engine_health("ghunt"):
                print(f"{C_RED}[ERROR] GHunt venv not found. Run Setup [Option 5] first.{C_RESET}")
                pause_prompt()
                continue

            clear_screen()

            if choice == "1":
                print(f"{C_GREEN}[+] Scanning email '{target_email}' across 120+ services...{C_RESET}")
                run_command_interactive([str(ENGINES["holehe"]["exe"]), target_email])
            elif choice == "2":
                print(f"{C_GREEN}[+] Scanning email '{target_email}' (showing used services only)...{C_RESET}")
                run_command_interactive([str(ENGINES["holehe"]["exe"]), "--only-used", target_email])
            elif choice == "3":
                print(f"{C_GREEN}[+] Running GHunt Google account reconnaissance on '{target_email}'...{C_RESET}")
                run_command_interactive([str(ENGINES["ghunt"]["exe"]), "email", target_email])
            elif choice == "4":
                run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--email", target_email])
            elif choice == "5":
                print(f"{C_CYAN}{C_BOLD}=== STAGE 1/3: DATA BOCOR & INFOSTEALER CHECK ==={C_RESET}")
                run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--email", target_email])
                print(f"\n{C_CYAN}{C_BOLD}=== STAGE 2/3: HOLEHE 120+ SITES RECONNAISSANCE ==={C_RESET}")
                run_command_interactive([str(ENGINES["holehe"]["exe"]), "--only-used", target_email])
                print(f"\n{C_CYAN}{C_BOLD}=== STAGE 3/3: GHUNT GOOGLE ARTIFACT INTELLIGENCE ==={C_RESET}")
                run_command_interactive([str(ENGINES["ghunt"]["exe"]), "email", target_email])
                print(f"\n{C_GREEN}[✓] Comprehensive Email Reconnaissance Complete!{C_RESET}")

            pause_prompt()

        elif choice == "6":
            if not check_engine_health("ghunt"):
                print(f"{C_RED}[ERROR] GHunt venv not found. Run Setup [Option 5] first.{C_RESET}")
                pause_prompt()
                continue
            clear_screen()
            print(f"{C_CYAN}{C_BOLD}=== GHUNT GOOGLE COOKIE AUTHENTICATION ==={C_RESET}")
            print(f"{C_WHITE}GHunt requires valid Google cookies once to query the Google API.{C_RESET}")
            run_command_interactive([str(ENGINES["ghunt"]["exe"]), "login"])
            pause_prompt()


def workflow_phone():
    while True:
        print_banner("Target Investigation > Phone Number Intelligence")
        print(f"{C_WHITE}{C_BOLD}Carrier lookup, spam risk score, Indonesian Telco & E-Wallet VA codes:{C_RESET}\n")
        print(f" {C_GREEN}[1]{C_RESET} Global Phone Profile  (Numint - carrier, line type, risk score)")
        print(f" {C_GREEN}[2]{C_RESET} Indonesian Phone & VA (Indo OSINT - Telco, PSTN region & E-Wallets)")
        print(f" {C_GREEN}[3]{C_RESET} 🚀 Dual Phone Intel   (Runs Numint + Indo OSINT Phone Analyzer)")
        print(f" {C_GREEN}[4]{C_RESET} Launch Numint Web UI  (Modern Interactive Dashboard on Port 8080)")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Previous Menu")
        print(f" {C_RED}[0]{C_RESET} Return to Main Menu")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            return "MAIN"

        if choice in ["1", "2", "3"]:
            phone = input(f"\n{C_WHITE}Enter target phone number (e.g. +628123456789 or 08123456789):{C_RESET} ").strip()
            if not phone:
                print(f"{C_RED}[!] Phone number cannot be empty.{C_RESET}")
                time.sleep(1)
                continue

            clear_screen()

            if choice == "1":
                if not check_engine_health("numint"):
                    print(f"{C_RED}[ERROR] Numint venv not found. Run Setup [Option 5] first.{C_RESET}")
                    pause_prompt()
                    continue
                print(f"{C_GREEN}[+] Running Numint scan on '{phone}'...{C_RESET}")
                run_command_interactive([str(ENGINES["numint"]["exe"]), "scan", phone])

            elif choice == "2":
                print(f"{C_GREEN}[+] Running Indo OSINT Phone & E-Wallet VA generator...{C_RESET}")
                run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--phone", phone])

            elif choice == "3":
                print(f"{C_CYAN}{C_BOLD}=== STAGE 1/2: NUMINT GLOBAL PHONE INTELLIGENCE ==={C_RESET}")
                if check_engine_health("numint"):
                    run_command_interactive([str(ENGINES["numint"]["exe"]), "scan", phone])
                else:
                    print(f"{C_YELLOW}[!] Numint not installed. Skipping stage 1.{C_RESET}")

                print(f"\n{C_CYAN}{C_BOLD}=== STAGE 2/2: INDONESIAN TELCO & E-WALLET VIRTUAL ACCOUNTS ==={C_RESET}")
                run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--phone", phone])
                print(f"\n{C_GREEN}[✓] Phone Intelligence Audit Complete!{C_RESET}")

            pause_prompt()

        elif choice == "4":
            launch_web_service("numint")
            pause_prompt()


def workflow_indonesia():
    while True:
        print_banner("Target Investigation > Indonesia OSINT & Data Bocor")
        print(f"{C_WHITE}{C_BOLD}Specialized Indonesian Regional Intelligence, Data Bocor & Offline Search:{C_RESET}\n")
        print(f" {C_GREEN}[1]{C_RESET} 🪪 NIK KTP Decoder          (16-digit: Prov/Kab/Kec, Birth, Weton, Age)")
        print(f" {C_GREEN}[2]{C_RESET} 🏛️ NIP ASN / PNS Decoder     (18-digit: Birthdate, TMT CPNS, BUP Pensiun)")
        print(f" {C_GREEN}[3]{C_RESET} 📱 Phone & E-Wallet VA       (Telco, PSTN Area, DANA/OVO/GoPay/Shopee)")
        print(f" {C_GREEN}[4]{C_RESET} 🚗 Plat Nomor TNKB Decoder   (Regional A-PY, Jadetabek Sub-Code, Samsat)")
        print(f" {C_GREEN}[5]{C_RESET} 🔎 Indonesian Registry Dorks (PDDikti, Mahkamah Agung, LPSE, AHU)")
        print(f" {C_GREEN}[6]{C_RESET} ⚠️ Data Bocor & Stealers     (Live XposedOrNot & Hudson Rock breach check)")
        print(f" {C_GREEN}[7]{C_RESET} 🗄️ Local Database Search     (Search private offline CSVs/dumps via FTS5)")
        print(f" {C_GREEN}[8]{C_RESET} 📥 Import CSV into Local DB  (Fast FTS5 indexer for private datasets)")
        print(f" {C_GREEN}[9]{C_RESET} 📊 Local DB Stats & Guide    (View records count, indexed files & paths)")
        print(f" {C_GREEN}[10]{C_RESET}📋 Interactive Indo CLI Menu  (Full interactive wizard)")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Previous Menu")
        print(f" {C_RED}[0]{C_RESET} Return to Main Menu")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            return "MAIN"

        cli_script = str(ENGINES["indo_osint"]["cli"])

        if choice == "1":
            nik = input(f"\n{C_WHITE}Enter 16-digit NIK KTP:{C_RESET} ").strip()
            if nik:
                clear_screen()
                run_command_interactive([sys.executable, cli_script, "--nik", nik])
                pause_prompt()
        elif choice == "2":
            nip = input(f"\n{C_WHITE}Enter 18-digit NIP ASN / PNS:{C_RESET} ").strip()
            if nip:
                clear_screen()
                run_command_interactive([sys.executable, cli_script, "--nip", nip])
                pause_prompt()
        elif choice == "3":
            phone = input(f"\n{C_WHITE}Enter Indonesian Phone Number (e.g. 081234567890):{C_RESET} ").strip()
            if phone:
                clear_screen()
                run_command_interactive([sys.executable, cli_script, "--phone", phone])
                pause_prompt()
        elif choice == "4":
            plate = input(f"\n{C_WHITE}Enter License Plate / Plat Nomor (e.g. B 1234 KAA):{C_RESET} ").strip()
            if plate:
                clear_screen()
                run_command_interactive([sys.executable, cli_script, "--plate", plate])
                pause_prompt()
        elif choice == "5":
            target = input(f"\n{C_WHITE}Enter Name or Organization to Dork:{C_RESET} ").strip()
            if target:
                open_web = input(f"{C_CYAN}Open dork links in default browser? (y/n) [default: y]:{C_RESET} ").strip().lower() != "n"
                cmd = [sys.executable, cli_script, "--dorks", target]
                if open_web:
                    cmd.append("--open")
                clear_screen()
                run_command_interactive(cmd)
                pause_prompt()
        elif choice == "6":
            email_target = input(f"\n{C_WHITE}Enter target Email to check breaches & stealers:{C_RESET} ").strip()
            if email_target:
                clear_screen()
                run_command_interactive([sys.executable, cli_script, "--email", email_target])
                pause_prompt()
        elif choice == "7":
            query = input(f"\n{C_WHITE}Enter search term (Name, NIK, Phone, Email, Plat):{C_RESET} ").strip()
            if query:
                clear_screen()
                run_command_interactive([sys.executable, cli_script, "--db-search", query])
                pause_prompt()
        elif choice == "8":
            csv_path = input(f"\n{C_WHITE}Enter absolute or relative path to CSV/TSV file:{C_RESET} ").strip().strip('"')
            if csv_path:
                clear_screen()
                run_command_interactive([sys.executable, cli_script, "--db-import", csv_path])
                pause_prompt()
        elif choice == "9":
            clear_screen()
            run_command_interactive([sys.executable, cli_script, "--db-stats"])
            pause_prompt()
        elif choice == "10":
            clear_screen()
            run_command_interactive([sys.executable, cli_script])
            pause_prompt()


def workflow_instagram():
    while True:
        print_banner("Target Investigation > Instagram Reconnaissance")
        print(f"{C_WHITE}{C_BOLD}Osintgram Instagram Intelligence & Session Management:{C_RESET}\n")
        print(f" {C_GREEN}[1]{C_RESET} Launch Osintgram Web UI (FastAPI Dashboard on Port 8000)")
        print(f" {C_GREEN}[2]{C_RESET} Login via Session ID    (Fast, recommended, bypasses challenge)")
        print(f" {C_GREEN}[3]{C_RESET} Login via Credentials   (Username & Password + 2FA)")
        print(f" {C_GREEN}[4]{C_RESET} View Session Status     (Check if instagrapi_session.json exists)")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Previous Menu")
        print(f" {C_RED}[0]{C_RESET} Return to Main Menu")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            return "MAIN"

        if choice == "1":
            launch_web_service("osintgram")
            pause_prompt()
        elif choice == "2":
            clear_screen()
            set_sess_script = ROOT_DIR / "Osintgram" / "scripts" / "set_session.py"
            run_command_interactive([str(ENGINES["osintgram"]["python"]), str(set_sess_script)])
            pause_prompt()
        elif choice == "3":
            clear_screen()
            login_script = ROOT_DIR / "Osintgram" / "scripts" / "instagrapi_login.py"
            run_command_interactive([str(ENGINES["osintgram"]["python"]), str(login_script)])
            pause_prompt()
        elif choice == "4":
            sess_path = ROOT_DIR / "Osintgram" / "config" / "instagrapi_session.json"
            if sess_path.exists():
                print(f"\n{C_GREEN}[✓] Active Instagram session found:{C_RESET} {sess_path}")
                print(f"    Size: {sess_path.stat().st_size} bytes | Last modified: {datetime.fromtimestamp(sess_path.stat().st_mtime)}")
            else:
                print(f"\n{C_YELLOW}[!] No saved Instagram session found.{C_RESET}")
                print(f"    Use Option [2] (Session ID) or Option [3] (Credentials) to authenticate.")
            pause_prompt()


def workflow_snoop():
    while True:
        print_banner("Target Investigation > Snoop Persona Footprint")
        print(f"{C_WHITE}{C_BOLD}Conservative, evidence-backed person and footprint audit:{C_RESET}\n")
        print(f" {C_GREEN}[1]{C_RESET} Fast Persona Audit  (Standard evidence scan)")
        print(f" {C_GREEN}[2]{C_RESET} Deep Persona Audit  (Exhaustive `--mode deep` inquiry)")
        print(f" {C_GREEN}[3]{C_RESET} Launch Snoop Web UI (Interactive Case Workspace on Port 8005)")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Previous Menu")
        print(f" {C_RED}[0]{C_RESET} Return to Main Menu")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            return "MAIN"

        if choice in ["1", "2"]:
            target_name = input(f"\n{C_WHITE}Enter target full name, alias, or handle:{C_RESET} ").strip()
            if not target_name:
                print(f"{C_RED}[!] Target name cannot be empty.{C_RESET}")
                time.sleep(1)
                continue

            if not check_engine_health("snoop"):
                print(f"{C_RED}[ERROR] Snoop venv not found. Run Setup [Option 5] first.{C_RESET}")
                pause_prompt()
                continue

            clear_screen()
            if choice == "1":
                print(f"{C_GREEN}[+] Running standard Snoop investigation for '{target_name}'...{C_RESET}")
                run_command_interactive([str(ENGINES["snoop"]["exe"]), target_name])
            elif choice == "2":
                print(f"{C_GREEN}[+] Running deep Snoop investigation for '{target_name}'...{C_RESET}")
                run_command_interactive([str(ENGINES["snoop"]["exe"]), target_name, "--mode", "deep"])

            pause_prompt()

        elif choice == "3":
            launch_web_service("snoop")
            pause_prompt()


def target_investigation_menu():
    while True:
        print_banner("Target-Oriented Investigation")
        print(f"{C_WHITE}{C_BOLD}Select your target intelligence type to start a guided workflow:{C_RESET}\n")
        print(f" {C_CYAN}[1]{C_RESET} 👤 Username OSINT         - Sherlock & Maigret (Dual-Engine Recon)")
        print(f" {C_CYAN}[2]{C_RESET} 📧 Email & Data Bocor     - Holehe, GHunt, XposedOrNot & Stealers")
        print(f" {C_CYAN}[3]{C_RESET} 📱 Phone Number Intel     - Numint (Carrier/Spam) & Indo Telco/VA")
        print(f" {C_CYAN}[4]{C_RESET} 🇮🇩 Indonesia Regional     - NIK KTP, NIP ASN, Plat Nomor & Dorks")
        print(f" {C_CYAN}[5]{C_RESET} 📸 Instagram Recon        - Osintgram Web Dashboard & Session Auth")
        print(f" {C_CYAN}[6]{C_RESET} 🕵️ Persona Footprint       - Snoop Evidence-Backed Public Profile Audit")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Main Menu")
        print(f" {C_RED}[0]{C_RESET} Exit Application")

        choice = input(f"\n{C_CYAN}Enter choice [1-6, B, 0]:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            sys.exit(0)

        res = None
        if choice == "1":
            res = workflow_username()
        elif choice == "2":
            res = workflow_email()
        elif choice == "3":
            res = workflow_phone()
        elif choice == "4":
            res = workflow_indonesia()
        elif choice == "5":
            res = workflow_instagram()
        elif choice == "6":
            res = workflow_snoop()

        if res == "MAIN":
            return


# ==============================================================================
# 2. INDIVIDUAL ENGINE WORKSPACES
# ==============================================================================

def individual_engines_menu():
    while True:
        print_banner("Individual Engine Workspaces")
        print(f"{C_WHITE}{C_BOLD}Launch any of the 8 engines directly in console:{C_RESET}\n")
        print(f" {C_GREEN}[1]{C_RESET} Sherlock Engine       - {ENGINES['sherlock']['desc']}")
        print(f" {C_GREEN}[2]{C_RESET} Maigret Engine        - {ENGINES['maigret']['desc']}")
        print(f" {C_GREEN}[3]{C_RESET} Holehe Engine         - {ENGINES['holehe']['desc']}")
        print(f" {C_GREEN}[4]{C_RESET} GHunt Engine          - {ENGINES['ghunt']['desc']}")
        print(f" {C_GREEN}[5]{C_RESET} Numint Engine         - {ENGINES['numint']['desc']}")
        print(f" {C_GREEN}[6]{C_RESET} Snoop Engine          - {ENGINES['snoop']['desc']}")
        print(f" {C_GREEN}[7]{C_RESET} Indo OSINT Suite      - {ENGINES['indo_osint']['desc']}")
        print(f" {C_GREEN}[8]{C_RESET} Osintgram CLI Tools   - {ENGINES['osintgram']['desc']}")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Main Menu")
        print(f" {C_RED}[0]{C_RESET} Exit Application")

        choice = input(f"\n{C_CYAN}Select engine [1-8, B, 0]:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            sys.exit(0)

        clear_screen()
        if choice == "1":
            if not check_engine_health("sherlock"):
                print(f"{C_RED}[ERROR] Sherlock venv not found. Run Setup first.{C_RESET}")
            else:
                u = input(f"{C_WHITE}Enter username to scan (or Enter for --help):{C_RESET} ").strip()
                cmd = [str(ENGINES["sherlock"]["exe"]), "--folderoutput", str(REPORTS_DIR), "--csv", "--xlsx", u] if u else [str(ENGINES["sherlock"]["exe"]), "--help"]
                run_command_interactive(cmd)
            pause_prompt()

        elif choice == "2":
            if not check_engine_health("maigret"):
                print(f"{C_RED}[ERROR] Maigret venv not found. Run Setup first.{C_RESET}")
            else:
                u = input(f"{C_WHITE}Enter username to scan (or Enter for --help):{C_RESET} ").strip()
                cmd = [str(ENGINES["maigret"]["exe"]), "--folderoutput", str(REPORTS_DIR), "--html", "--pdf", u] if u else [str(ENGINES["maigret"]["exe"]), "--help"]
                run_command_interactive(cmd)
            pause_prompt()

        elif choice == "3":
            if not check_engine_health("holehe"):
                print(f"{C_RED}[ERROR] Holehe venv not found. Run Setup first.{C_RESET}")
            else:
                e = input(f"{C_WHITE}Enter email to check (or Enter for --help):{C_RESET} ").strip()
                cmd = [str(ENGINES["holehe"]["exe"]), "--only-used", e] if e else [str(ENGINES["holehe"]["exe"]), "--help"]
                run_command_interactive(cmd)
            pause_prompt()

        elif choice == "4":
            if not check_engine_health("ghunt"):
                print(f"{C_RED}[ERROR] GHunt venv not found. Run Setup first.{C_RESET}")
            else:
                print(f" {C_GREEN}[1]{C_RESET} Check Email (`ghunt email <email>`)")
                print(f" {C_GREEN}[2]{C_RESET} Check GAIA ID (`ghunt gaia <id>`)")
                print(f" {C_GREEN}[3]{C_RESET} Authenticate Cookies (`ghunt login`)")
                sub = input(f"{C_CYAN}Select GHunt command [1-3]:{C_RESET} ").strip()
                if sub == "1":
                    em = input("Enter email: ").strip()
                    run_command_interactive([str(ENGINES["ghunt"]["exe"]), "email", em])
                elif sub == "2":
                    gaia = input("Enter GAIA ID: ").strip()
                    run_command_interactive([str(ENGINES["ghunt"]["exe"]), "gaia", gaia])
                elif sub == "3":
                    run_command_interactive([str(ENGINES["ghunt"]["exe"]), "login"])
            pause_prompt()

        elif choice == "5":
            if not check_engine_health("numint"):
                print(f"{C_RED}[ERROR] Numint venv not found. Run Setup first.{C_RESET}")
            else:
                p = input(f"{C_WHITE}Enter phone number (e.g. +628123456789 or Enter for --help):{C_RESET} ").strip()
                cmd = [str(ENGINES["numint"]["exe"]), "scan", p] if p else [str(ENGINES["numint"]["exe"]), "--help"]
                run_command_interactive(cmd)
            pause_prompt()

        elif choice == "6":
            if not check_engine_health("snoop"):
                print(f"{C_RED}[ERROR] Snoop venv not found. Run Setup first.{C_RESET}")
            else:
                n = input(f"{C_WHITE}Enter person name / handle (or Enter for doctor):{C_RESET} ").strip()
                cmd = [str(ENGINES["snoop"]["exe"]), n] if n else [str(ENGINES["snoop"]["exe"]), "doctor"]
                run_command_interactive(cmd)
            pause_prompt()

        elif choice == "7":
            run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"])])
            pause_prompt()

        elif choice == "8":
            workflow_instagram()


# ==============================================================================
# 3. WEB DASHBOARDS HUB
# ==============================================================================

def launch_web_service(service_key: str):
    service = WEB_SERVICES.get(service_key)
    if not service:
        print(f"{C_RED}[ERROR] Unknown web service: {service_key}{C_RESET}")
        return

    port = service["port"]
    url = service["url"]
    name = service["name"]

    print(f"\n{C_CYAN}[i] Checking status for {name} (Port {port})...{C_RESET}")
    if is_port_listening(port):
        print(f"{C_GREEN}[✓] {name} is ALREADY RUNNING on {url}{C_RESET}")
        print(f"{C_BLUE}[i] Opening {url} in your default browser...{C_RESET}")
        webbrowser.open(url)
        return

    # Check venv
    if service_key == "maigret" and not check_engine_health("maigret"):
        print(f"{C_RED}[ERROR] Maigret venv not found. Run Setup first.{C_RESET}")
        return
    elif service_key == "osintgram" and not check_engine_health("osintgram"):
        print(f"{C_RED}[ERROR] Osintgram venv not found. Run Setup first.{C_RESET}")
        return
    elif service_key == "numint" and not check_engine_health("numint"):
        print(f"{C_RED}[ERROR] Numint venv not found. Run Setup first.{C_RESET}")
        return
    elif service_key == "snoop" and not check_engine_health("snoop"):
        print(f"{C_RED}[ERROR] Snoop venv not found. Run Setup first.{C_RESET}")
        return

    print(f"{C_GREEN}[+] Starting {name} in a new window...{C_RESET}")
    if sys.platform == "win32":
        cmd_str = " ".join(f'"{c}"' for c in service["cmd"])
        subprocess.Popen(
            f'start "{name} - Port {port}" {cmd_str}',
            cwd=str(service["cwd"]),
            shell=True
        )
    else:
        subprocess.Popen(service["cmd"], cwd=str(service["cwd"]))

    print(f"{C_DIM}Waiting for web server to bind to port {port}...{C_RESET}")
    bound = False
    for _ in range(12):
        time.sleep(1)
        if is_port_listening(port):
            bound = True
            break

    if bound:
        print(f"{C_GREEN}[✓] {name} is successfully ONLINE!{C_RESET}")
    else:
        print(f"{C_YELLOW}[!] Server launched. Port {port} should open momentarily.{C_RESET}")

    print(f"{C_BLUE}[i] Opening {url} in your default browser...{C_RESET}")
    webbrowser.open(url)


def web_dashboards_menu():
    while True:
        print_banner("Web Dashboards Hub")
        print(f"{C_WHITE}{C_BOLD}Launch and manage browser graphical interfaces:{C_RESET}\n")

        for key, s in WEB_SERVICES.items():
            running = is_port_listening(s["port"])
            status_tag = f"{C_GREEN}[● RUNNING]{C_RESET}" if running else f"{C_DIM}[○ STOPPED]{C_RESET}"
            print(f" {status_tag} {C_WHITE}{s['name']:<25}{C_RESET} -> {C_CYAN}{s['url']}{C_RESET}")

        print(f"\n{C_DIM}" + "-" * 76 + f"{C_RESET}")
        print(f" {C_GREEN}[1]{C_RESET} Launch Maigret Web UI        (Port 5000)")
        print(f" {C_GREEN}[2]{C_RESET} Launch Osintgram Web UI       (Port 8000)")
        print(f" {C_GREEN}[3]{C_RESET} Launch Numint Web UI          (Port 8080)")
        print(f" {C_GREEN}[4]{C_RESET} Launch Snoop Web UI           (Port 8005)")
        print(f" {C_GREEN}[5]{C_RESET} Launch ALL 4 Web Dashboards   (One-Click Multi-Launch)")
        print(f" {C_GREEN}[R]{C_RESET} Refresh Port Status")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Main Menu")
        print(f" {C_RED}[0]{C_RESET} Exit Application")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            sys.exit(0)
        if choice == "r":
            continue

        if choice == "1":
            launch_web_service("maigret")
            pause_prompt()
        elif choice == "2":
            launch_web_service("osintgram")
            pause_prompt()
        elif choice == "3":
            launch_web_service("numint")
            pause_prompt()
        elif choice == "4":
            launch_web_service("snoop")
            pause_prompt()
        elif choice == "5":
            for k in ["maigret", "osintgram", "numint", "snoop"]:
                launch_web_service(k)
            pause_prompt()


# ==============================================================================
# 4. EVIDENCE LOCKER & REPORTS VIEWER
# ==============================================================================

def reports_viewer_menu():
    while True:
        print_banner("Evidence Locker & Reports Viewer")
        print(f"{C_WHITE}{C_BOLD}Centralized Intelligence Reports Archive (`reports/`):{C_RESET}\n")

        patterns = ["*.html", "*.csv", "*.xlsx", "*.json", "*.txt", "*.pdf"]
        files = []
        for pat in patterns:
            files.extend(list(REPORTS_DIR.glob(f"**/{pat}")))

        files = [f for f in files if f.name not in [".gitkeep", ".gitignore"] and not f.name.startswith(".")]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        if not files:
            print(f" {C_YELLOW}[i] No reports generated yet. Run a search to populate this locker!{C_RESET}")
        else:
            print(f" Found {C_GREEN}{len(files)}{C_RESET} intelligence artifact(s):\n")
            display_count = min(len(files), 15)
            for idx, f in enumerate(files[:display_count], 1):
                mod_time = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                size_kb = f.stat().st_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{f.stat().st_size} B"
                print(f"  {C_CYAN}[{idx:2d}]{C_RESET} {C_WHITE}{f.name:<38}{C_RESET} {C_DIM}({size_str}, {mod_time}){C_RESET}")

        print(f"\n{C_DIM}" + "-" * 76 + f"{C_RESET}")
        print(f" {C_GREEN}[O]{C_RESET} Open Reports Folder in Windows Explorer")
        print(f" {C_GREEN}[L]{C_RESET} Open Latest Generated Report")
        print(f" {C_GREEN}[#]{C_RESET} Enter file number to open specific report")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Previous Menu")
        print(f" {C_RED}[0]{C_RESET} Exit Application")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            sys.exit(0)

        if choice == "o":
            if sys.platform == "win32":
                os.startfile(str(REPORTS_DIR))
            else:
                webbrowser.open(str(REPORTS_DIR))
        elif choice == "l":
            if files:
                latest = files[0]
                print(f"{C_GREEN}[+] Opening latest report: {latest.name}...{C_RESET}")
                if sys.platform == "win32":
                    os.startfile(str(latest))
                else:
                    webbrowser.open(str(latest))
            else:
                print(f"{C_RED}[!] No reports found to open.{C_RESET}")
                time.sleep(1)
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(files):
                selected = files[idx - 1]
                print(f"{C_GREEN}[+] Opening report: {selected.name}...{C_RESET}")
                if sys.platform == "win32":
                    os.startfile(str(selected))
                else:
                    webbrowser.open(str(selected))
            else:
                print(f"{C_RED}[!] Invalid report number.{C_RESET}")
                time.sleep(1)


# ==============================================================================
# 5. SYSTEM DIAGNOSTICS & SETUP
# ==============================================================================

def run_automated_setup():
    """Provision virtual environments and install all dependencies for all 8 engines."""
    print_banner("Automated Setup Wizard")
    print(f"{C_WHITE}{C_BOLD}Provisioning isolated virtual environments & installing dependencies:{C_RESET}\n")

    steps = [
        ("Sherlock", "sherlock", ["-e", str(ROOT_DIR / "sherlock")]),
        ("Maigret", "maigret", ["-e", str(ROOT_DIR / "maigret")]),
        ("Osintgram", "Osintgram", ["-r", str(ROOT_DIR / "Osintgram" / "requirements.txt")]),
        ("Numint", "numint", ["-e", f"{ROOT_DIR / 'numint'}[web,pdf]"]),
        ("Snoop", "snoop", ["-e", f"{ROOT_DIR / 'snoop'}[pdf]"]),
        ("Holehe", "holehe", ["-e", str(ROOT_DIR / "holehe")]),
        ("GHunt", "GHunt", ["-e", str(ROOT_DIR / "GHunt")]),
    ]

    for idx, (name, folder, install_args) in enumerate(steps, 1):
        venv_dir = ROOT_DIR / folder / ".venv"
        print(f"[{idx}/{len(steps)}] Setting up {name}...")
        if not venv_dir.exists():
            print(f"      Creating virtual environment: {venv_dir}...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)])

        pip_exe = venv_dir / "Scripts" / "pip.exe"
        if pip_exe.exists():
            print(f"      Installing dependencies...")
            subprocess.run([str(pip_exe), "install", "--upgrade", "pip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            res = subprocess.run([str(pip_exe), "install"] + install_args)
            if res.returncode == 0:
                print(f"      {C_GREEN}[OK] {name} setup complete.{C_RESET}\n")
            else:
                print(f"      {C_YELLOW}[!] {name} installed with warnings.{C_RESET}\n")
        else:
            print(f"      {C_RED}[ERROR] Failed to locate pip in {venv_dir}{C_RESET}\n")

    # Osintgram initial config
    cfg_ex = ROOT_DIR / "Osintgram" / "config" / "credentials.ini.example"
    cfg_dst = ROOT_DIR / "Osintgram" / "config" / "credentials.ini"
    if cfg_ex.exists() and not cfg_dst.exists():
        shutil.copy(cfg_ex, cfg_dst)
        print("      Created Osintgram credentials.ini template.")

    print(f"{C_GREEN}{C_BOLD}[✓] Indonesia OSINT Suite (indo_osint) uses standard library [READY].{C_RESET}\n")
    print(f"{C_GREEN}{C_BOLD}======================================================================{C_RESET}")
    print(f"{C_GREEN}{C_BOLD}             AUTOMATED SETUP COMPLETED SUCCESSFULLY!                  {C_RESET}")
    print(f"{C_GREEN}{C_BOLD}======================================================================{C_RESET}")


def system_diagnostics_menu():
    while True:
        print_banner("System Diagnostics & Health Check")
        print(f"{C_WHITE}{C_BOLD}Virtual Environment Status & Integrity Inspection:{C_RESET}\n")

        print(f" {'Engine':<16} | {'Environment Path':<40} | {'Status'}")
        print(f" " + "-" * 72)

        all_ok = True
        for key, e in ENGINES.items():
            ok = check_engine_health(key)
            if not ok:
                all_ok = False
            status_text = f"{C_GREEN}● READY{C_RESET}" if ok else f"{C_RED}○ MISSING{C_RESET}"
            path_display = str(e.get("exe") or e.get("uvicorn") or e.get("cli") or "").replace(str(ROOT_DIR), ".")
            if len(path_display) > 38:
                path_display = "..." + path_display[-35:]
            print(f" {e['name']:<16} | {path_display:<40} | {status_text}")

        print(f"\n{C_DIM}" + "-" * 76 + f"{C_RESET}")
        overall = f"{C_GREEN}[✓] ALL 8 ENGINES OPERATIONAL{C_RESET}" if all_ok else f"{C_YELLOW}[!] SOME ENGINES NEED SETUP{C_RESET}"
        print(f" System Status: {overall}")
        print(f" Python Executable: {sys.executable} ({sys.version.split()[0]})")
        print(f" Toolkit Root: {ROOT_DIR}\n")

        print(f" {C_GREEN}[1]{C_RESET} Run Automated Setup Wizard   (Provision / Repair all 8 venvs)")
        print(f" {C_GREEN}[2]{C_RESET} Launch OSINT Terminal Shell  (cmd with all 8 venvs in PATH)")
        print(f" {C_GREEN}[R]{C_RESET} Refresh Diagnostics")
        print(f"\n {C_YELLOW}[B]{C_RESET} Back to Main Menu")
        print(f" {C_RED}[0]{C_RESET} Exit Application")

        choice = input(f"\n{C_CYAN}Select option:{C_RESET} ").strip().lower()
        if choice in ["b", "back"]:
            return
        if choice == "0":
            sys.exit(0)
        if choice == "r":
            continue

        if choice == "1":
            clear_screen()
            run_automated_setup()
            pause_prompt()
        elif choice == "2":
            clear_screen()
            print(f"{C_CYAN}[+] Spawning Developer OSINT Terminal...{C_RESET}")
            scripts_paths = [
                str(ROOT_DIR / "sherlock" / ".venv" / "Scripts"),
                str(ROOT_DIR / "maigret" / ".venv" / "Scripts"),
                str(ROOT_DIR / "Osintgram" / ".venv" / "Scripts"),
                str(ROOT_DIR / "numint" / ".venv" / "Scripts"),
                str(ROOT_DIR / "snoop" / ".venv" / "Scripts"),
                str(ROOT_DIR / "holehe" / ".venv" / "Scripts"),
                str(ROOT_DIR / "GHunt" / ".venv" / "Scripts"),
            ]
            env = os.environ.copy()
            env["PATH"] = ";".join(scripts_paths) + ";" + env.get("PATH", "")
            subprocess.run(["cmd.exe", "/k", "title OSINT Developer Shell & echo [OSINT Shell Active] sherlock, maigret, holehe, ghunt, numint, snoop ready in PATH."], env=env, cwd=str(ROOT_DIR))


# ==============================================================================
# MAIN APPLICATION CONTROLLER
# ==============================================================================

def main_menu():
    while True:
        print_banner("Main Navigation")
        print(f"{C_WHITE}{C_BOLD}Select an operation mode to begin:{C_RESET}\n")
        print(f" {C_CYAN}[1]{C_RESET} 🎯 {C_BOLD}TARGET INVESTIGATION{C_RESET}       (Guided search: Username, Email/Breaches, Phone, NIK, etc.)")
        print(f" {C_CYAN}[2]{C_RESET} ⚙️  {C_BOLD}INDIVIDUAL WORKSPACES{C_RESET}      (Direct CLI for Sherlock, Maigret, Holehe, GHunt, etc.)")
        print(f" {C_CYAN}[3]{C_RESET} 🌐 {C_BOLD}WEB DASHBOARDS HUB{C_RESET}         (One-Click Launch: Ports 5000, 8000, 8080, 8005)")
        print(f" {C_CYAN}[4]{C_RESET} 📁 {C_BOLD}EVIDENCE & REPORTS LOCKER{C_RESET}  (View generated HTML/CSV/XLSX intelligence)")
        print(f" {C_CYAN}[5]{C_RESET} 🩺 {C_BOLD}HEALTH & SYSTEM DIAGNOSTICS{C_RESET}(Verify all 8 venvs, run setup, or open shell)")
        print(f"\n {C_RED}[0]{C_RESET} 🚪 Exit Application")
        print(f"{C_DIM}" + "-" * 76 + f"{C_RESET}")

        try:
            choice = input(f"{C_CYAN}Enter choice [0-5]:{C_RESET} ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_YELLOW}Goodbye!{C_RESET}")
            sys.exit(0)

        if choice == "1":
            target_investigation_menu()
        elif choice == "2":
            individual_engines_menu()
        elif choice == "3":
            web_dashboards_menu()
        elif choice == "4":
            reports_viewer_menu()
        elif choice == "5":
            system_diagnostics_menu()
        elif choice in ["0", "exit", "quit", "q"]:
            clear_screen()
            print(f"{C_GREEN}Thank you for using the OSINT Toolkit. Stay safe!{C_RESET}\n")
            sys.exit(0)
        else:
            print(f"{C_RED}[!] Invalid choice. Please enter 0, 1, 2, 3, 4, or 5.{C_RESET}")
            time.sleep(1)


if __name__ == "__main__":
    import argparse

    # Quick direct tool CLI dispatcher (run.bat sherlock / maigret / holehe / ghunt / numint / snoop / indo)
    if len(sys.argv) > 1:
        first_arg = sys.argv[1].lower().strip()
        remaining_args = sys.argv[2:]

        if first_arg == "sherlock":
            cmd = [str(ENGINES["sherlock"]["exe"]), "--folderoutput", str(REPORTS_DIR), "--csv", "--xlsx"] + remaining_args if remaining_args else [str(ENGINES["sherlock"]["exe"]), "--help"]
            sys.exit(run_command_interactive(cmd))
        elif first_arg == "maigret":
            cmd = [str(ENGINES["maigret"]["exe"]), "--folderoutput", str(REPORTS_DIR), "--html", "--pdf"] + remaining_args if remaining_args else [str(ENGINES["maigret"]["exe"]), "--help"]
            sys.exit(run_command_interactive(cmd))
        elif first_arg == "holehe":
            cmd = [str(ENGINES["holehe"]["exe"])] + remaining_args if remaining_args else [str(ENGINES["holehe"]["exe"]), "--help"]
            sys.exit(run_command_interactive(cmd))
        elif first_arg == "ghunt":
            cmd = [str(ENGINES["ghunt"]["exe"])] + remaining_args if remaining_args else [str(ENGINES["ghunt"]["exe"]), "--help"]
            sys.exit(run_command_interactive(cmd))
        elif first_arg == "numint":
            cmd = [str(ENGINES["numint"]["exe"])] + remaining_args if remaining_args else [str(ENGINES["numint"]["exe"]), "--help"]
            sys.exit(run_command_interactive(cmd))
        elif first_arg == "snoop":
            cmd = [str(ENGINES["snoop"]["exe"])] + remaining_args if remaining_args else [str(ENGINES["snoop"]["exe"]), "doctor"]
            sys.exit(run_command_interactive(cmd))
        elif first_arg in ["indo", "indo_osint"]:
            cmd = [sys.executable, str(ENGINES["indo_osint"]["cli"])] + remaining_args
            sys.exit(run_command_interactive(cmd))
        elif first_arg == "osintgram":
            if "web" in remaining_args:
                launch_web_service("osintgram")
                sys.exit(0)
            workflow_instagram()
            sys.exit(0)

    parser = argparse.ArgumentParser(
        description="OSINT Toolkit - All-in-One Master Navigator (8 Engines)",
        add_help=True
    )
    parser.add_argument("--diag", "-d", action="store_true", help="Print system health & environment diagnostics")
    parser.add_argument("--setup", action="store_true", help="Run automated setup for all 8 engines")
    parser.add_argument("--web", "-w", choices=["maigret", "osintgram", "numint", "snoop", "all"], help="Launch a web dashboard")
    parser.add_argument("--username", "-u", type=str, help="Quick dual-scan for username (Sherlock + Maigret)")
    parser.add_argument("--email", "-e", type=str, help="Quick email reconnaissance (Holehe + GHunt)")
    parser.add_argument("--breach", type=str, help="Live Data Bocor and infostealer malware check (XposedOrNot + Hudson Rock)")
    parser.add_argument("--phone", "-p", type=str, help="Quick phone intelligence scan (Numint + Indo OSINT)")
    parser.add_argument("--nik", type=str, help="Decode 16-digit Indonesian NIK KTP")
    parser.add_argument("--db-search", type=str, help="Search local private offline database (FTS5)")
    parser.add_argument("--db-import", type=str, help="Import a CSV dataset into local private database")
    parser.add_argument("--db-stats", action="store_true", help="Show local private database statistics")

    args, unknown = parser.parse_known_args()

    try:
        if args.diag:
            print_banner("System Diagnostics")
            print(f"{C_WHITE}{C_BOLD}Virtual Environment Status & Integrity Inspection:{C_RESET}\n")
            print(f" {'Engine':<16} | {'Status'}")
            print(f" " + "-" * 32)
            all_ok = True
            for k, e in ENGINES.items():
                ok = check_engine_health(k)
                if not ok:
                    all_ok = False
                status = f"{C_GREEN}● READY{C_RESET}" if ok else f"{C_RED}○ MISSING{C_RESET}"
                print(f" {e['name']:<16} | {status}")
            print(f"\n Python: {sys.executable} ({sys.version.split()[0]})")
            sys.exit(0 if all_ok else 1)

        elif args.setup:
            run_automated_setup()
            sys.exit(0)

        elif args.web:
            if args.web == "all":
                for svc in ["maigret", "osintgram", "numint", "snoop"]:
                    launch_web_service(svc)
            else:
                launch_web_service(args.web)
            sys.exit(0)

        elif args.username:
            print(f"{C_CYAN}{C_BOLD}=== QUICK DUAL SCAN: {args.username} ==={C_RESET}")
            run_command_interactive([str(ENGINES["sherlock"]["exe"]), "--folderoutput", str(REPORTS_DIR), "--csv", "--xlsx", args.username])
            run_command_interactive([str(ENGINES["maigret"]["exe"]), "--folderoutput", str(REPORTS_DIR), "--html", "--pdf", args.username])
            sys.exit(0)

        elif args.email:
            print(f"{C_CYAN}{C_BOLD}=== QUICK EMAIL RECON: {args.email} ==={C_RESET}")
            run_command_interactive([str(ENGINES["holehe"]["exe"]), "--only-used", args.email])
            run_command_interactive([str(ENGINES["ghunt"]["exe"]), "email", args.email])
            sys.exit(0)

        elif args.breach:
            run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--email", args.breach])
            sys.exit(0)

        elif args.phone:
            print(f"{C_CYAN}{C_BOLD}=== QUICK PHONE INTEL: {args.phone} ==={C_RESET}")
            if check_engine_health("numint"):
                run_command_interactive([str(ENGINES["numint"]["exe"]), "scan", args.phone])
            run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--phone", args.phone])
            sys.exit(0)

        elif args.nik:
            run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--nik", args.nik])
            sys.exit(0)

        elif args.db_search:
            run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--db-search", args.db_search])
            sys.exit(0)

        elif args.db_import:
            run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--db-import", args.db_import])
            sys.exit(0)

        elif args.db_stats:
            run_command_interactive([sys.executable, str(ENGINES["indo_osint"]["cli"]), "--db-stats"])
            sys.exit(0)

        else:
            main_menu()

    except (KeyboardInterrupt, EOFError):
        print(f"\n{C_YELLOW}Exiting OSINT Toolkit.{C_RESET}")
        sys.exit(0)
