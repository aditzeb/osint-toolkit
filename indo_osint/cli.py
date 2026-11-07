#!/usr/bin/env python3
"""Interactive & CLI Runner for the Indonesian OSINT Intelligence Suite."""

import argparse
import os
import sys
import webbrowser
from pathlib import Path

# Ensure parent directory is importable when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indo_osint.nik_parser import parse_nik
from indo_osint.phone_intel import analyze_indo_phone
from indo_osint.plate_decoder import decode_plate
from indo_osint.registry_dorks import generate_indo_dorks, parse_nip_asn
from indo_osint.breach_lookup import lookup_email_full
from indo_osint.db_search import (
    search_local_db,
    import_csv_file,
    get_db_stats,
    DATA_DIR,
    DB_PATH,
)

# Enable ANSI escape codes on Windows 10/11
if os.name == "nt":
    os.system("")

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner() -> None:
    print(f"{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}                 INDONESIA OSINT INTELLIGENCE SUITE                   {RESET}")
    print(f"{DIM}   NIK | NIP | Phone/VA | Plat | Dorks | Data Bocor | Local DB Search {RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")


def render_nik(nik_str: str) -> None:
    data = parse_nik(nik_str)
    print(f"\n{BOLD}[+] NIK KTP ANALYSIS: {CYAN}{data.get('cleaned_nik')}{RESET}")
    print("-" * 70)
    if not data["valid"]:
        print(f"{RED}[!] Status          : INVALID NIK{RESET}")
        for err in data["errors"]:
            print(f"{RED}    - {err}{RESET}")
        return

    print(f"{GREEN}[✓] Status          : VALID FORMAT{RESET}")
    print(f"    Provinsi        : {BOLD}{data['province_name']}{RESET} (Code: {data['province_code']})")
    print(f"    Kabupaten/Kota  : {BOLD}{data['kabupaten_name']}{RESET} (Code: {data['kabupaten_code']})")
    print(f"    Kecamatan       : {BOLD}{data['kecamatan_name']}{RESET}")
    print(f"    Jenis Kelamin   : {BOLD}{data['gender']}{RESET}")
    print(f"    Tanggal Lahir   : {BOLD}{data['birthdate']}{RESET} ({data['age']})")
    print(f"    Hari & Weton    : {data['day_of_week']} | Weton Jawa: {YELLOW}{data['weton_jawa']}{RESET}")
    print(f"    Zodiak & Gen    : {data['zodiac']} | {data['generation']}")
    print(f"    Urutan Dukcapil : #{data['sequence']}")

    if data["warnings"]:
        print(f"\n{YELLOW}[!] Notes:{RESET}")
        for w in data["warnings"]:
            print(f"    - {w}")

    print(f"\n{CYAN}[*] Official Verification Portals:{RESET}")
    for label, link in data["verification_links"].items():
        print(f"    - {label:<22}: {link}")
    print("-" * 70)


def render_nip(nip_str: str) -> None:
    data = parse_nip_asn(nip_str)
    print(f"\n{BOLD}[+] NIP ASN / PNS ANALYSIS: {CYAN}{data.get('cleaned_nip')}{RESET}")
    print("-" * 70)
    if not data["valid"]:
        print(f"{RED}[!] Status          : INVALID NIP ASN{RESET}")
        for err in data["errors"]:
            print(f"{RED}    - {err}{RESET}")
        return

    print(f"{GREEN}[✓] Status          : VALID 18-DIGIT NIP FORMAT{RESET}")
    print(f"    Tanggal Lahir   : {BOLD}{data.get('birthdate')}{RESET} ({data.get('age')})")
    print(f"    Jenis Kelamin   : {BOLD}{data.get('gender')}{RESET}")
    print(f"    TMT CPNS        : {BOLD}{data.get('cpns_appointment')}{RESET} ({data.get('years_of_service')} Masa Kerja)")
    print(f"    Usia Saat CPNS  : {data.get('age_at_appointment')}")
    print(f"    Est. Pensiun    : Tahun {data.get('retirement_year_est')} (BUP 58 Tahun)")
    print(f"    Nomor Urut      : #{data.get('sequence')}")
    print("-" * 70)


def render_phone(phone_str: str) -> None:
    data = analyze_indo_phone(phone_str)
    print(f"\n{BOLD}[+] INDONESIAN PHONE & E-WALLET INTELLIGENCE: {CYAN}{data['international_format']}{RESET}")
    print("-" * 70)
    print(f"    Format Lokal    : {BOLD}{data['local_format']}{RESET}")
    print(f"    Format Intl     : {BOLD}{data['international_format']}{RESET}")
    print(f"    WhatsApp JID    : {data['whatsapp_id']}")
    print(f"    Tipe Jaringan   : {data['type']}")
    print(f"    Operator        : {GREEN}{BOLD}{data['operator']}{RESET}")
    print(f"    Produk / Kartu  : {YELLOW}{data['brand']}{RESET} ({data['billing_model']})")
    print(f"    Wilayah / Area  : {data['region']}")

    if data.get("ewallet_va_inquiry_codes"):
        print(f"\n{CYAN}{BOLD}[*] E-Wallet Virtual Account (VA) Name-Resolution Numbers:{RESET}")
        print(f"{DIM}    (Enter these VA codes in M-Banking transfer inquiry to see the registered owner's real name){RESET}")
        for label, va in data["ewallet_va_inquiry_codes"].items():
            print(f"    - {label:<24}: {BOLD}{va}{RESET}")

    print(f"\n{CYAN}{BOLD}[*] OSINT Pivot Links & Fraud Checks:{RESET}")
    for label, link in data["osint_links"].items():
        print(f"    - {label:<38}: {link}")
    print("-" * 70)


def render_plate(plate_str: str) -> None:
    data = decode_plate(plate_str)
    print(f"\n{BOLD}[+] INDONESIAN VEHICLE LICENSE PLATE (TNKB): {CYAN}{data.get('formatted_plate', plate_str)}{RESET}")
    print("-" * 70)
    if "error" in data:
        print(f"{RED}[!] {data['error']}{RESET}")
        return

    print(f"    Kode Wilayah    : {BOLD}{data['prefix']}{RESET} -> {GREEN}{BOLD}{data['region']}{RESET}")
    print(f"    Sub-Wilayah     : {BOLD}{data['sub_region_samsat']}{RESET}")
    print(f"    Nomor Polisi    : {data['number']} ({data['number_allocation_class']})")
    print(f"    Seri Huruf Akhir: {BOLD}{data['suffix']}{RESET}")
    print(f"    Jenis Kendaraan : {YELLOW}{data['specific_vehicle_type']}{RESET}")
    print(f"    Portal E-Samsat : {CYAN}{data['samsat_portal']}{RESET}")
    print(f"    Samsat Nasional : {data['national_app']}")
    print("-" * 70)


def render_dorks(query: str, open_browser: bool = False) -> None:
    dorks = generate_indo_dorks(query)
    print(f"\n{BOLD}[+] INDONESIAN REGISTRY & ACADEMIC DORKS FOR: {CYAN}{query}{RESET}")
    print("-" * 70)
    first_links = []
    for category, items in dorks.items():
        print(f"\n{YELLOW}{BOLD}  [{category}]{RESET}")
        for name, url in items.items():
            print(f"    - {name:<42}: {url}")
            first_links.append(url)
    print("-" * 70)

    if open_browser and first_links:
        print(f"{GREEN}[*] Opening PDDikti & Mahkamah Agung search tabs in your browser...{RESET}")
        webbrowser.open(dorks["Education & Academic (PDDikti & Kampus)"]["PDDikti Kemdiktisaintek Portal"])
        webbrowser.open(dorks["Legal & Court Records (Mahkamah Agung & SIPP)"]["Direktori Putusan Mahkamah Agung"])


def render_breach(email_str: str) -> None:
    print(f"\n{BOLD}[+] SCANNING BREACHES & INFOSTEALERS FOR: {CYAN}{email_str}{RESET}...")
    intel = lookup_email_full(email_str)
    print("-" * 70)

    # 1. Profile intelligence (Gravatar & GitHub)
    grav = intel["gravatar"]
    gh = intel["github"]
    if grav["found"] or gh["found"]:
        print(f"{GREEN}{BOLD}[👤 IDENTITY & PROFILE LINKING]{RESET}")
        if grav["found"]:
            if grav["display_name"] or grav["full_name"]:
                print(f"    Real Name       : {BOLD}{grav['full_name'] or grav['display_name']}{RESET}")
            if grav["about"]:
                print(f"    Bio / About     : {grav['about']}")
            if grav["accounts"]:
                print(f"    Linked Accounts : {', '.join(grav['accounts'][:3])}")
            print(f"    Gravatar Avatar : {grav['avatar_url']}")

        if gh["found"]:
            names_str = ", ".join(gh["names"]) if gh["names"] else "N/A"
            users_str = ", ".join(gh["usernames"]) if gh["usernames"] else "N/A"
            repos_str = ", ".join(gh["recent_repos"][:3]) if gh["recent_repos"] else "N/A"
            print(f"    GitHub Commits  : {gh['commit_count']} public commit(s)")
            print(f"    Git Author Name : {names_str}")
            print(f"    GitHub Handle   : {users_str}")
            print(f"    Active Repos    : {repos_str}")
        print()

    # 2. XposedOrNot Data Breaches
    xp = intel["xposed"]
    if xp["found"]:
        print(f"{RED}{BOLD}[⚠️  DATA BOCOR / KNOWN BREACHES: {xp['breach_count']} EXPOSURES]{RESET}")
        print(f"    Risk Score      : {YELLOW}{xp['risk_score']}{RESET}")
        if xp["exposed_fields"]:
            print(f"    Exposed Data    : {BOLD}{', '.join(xp['exposed_fields'])}{RESET}")

        print(f"\n    {'Breach Name':<28} | {'Date':<12} | {'Domain'}")
        print("    " + "-" * 62)
        for b in xp["breaches"][:15]:
            # Highlight Indonesian breaches
            b_name = b["name"]
            if any(id_site in b_name.lower() for id_site in ["tokopedia", "bukalapak", "bhinneka", "kpu", "bpjs", "reddoorz"]):
                b_name = f"{RED}{BOLD}{b_name} [ID]{RESET}"
            print(f"    {b_name:<28} | {b['date']:<12} | {b.get('domain', '')}")

        if len(xp["breaches"]) > 15:
            print(f"    ... and {len(xp['breaches']) - 15} more breach occurrences.")
    else:
        print(f"{GREEN}[✓] Data Breaches   : No public breach records detected on XposedOrNot.{RESET}")

    print()

    # 3. Hudson Rock Infostealer Malware Compromise
    hr = intel["hudsonrock"]
    if hr["compromised"]:
        print(f"{RED}{BOLD}[☠️  INFOSTEALER MALWARE INFECTION DETECTED: {hr['stealer_count']} INFECTION(S)]{RESET}")
        print(f"    Corporate Logins: {hr['total_corp_services']} | User Logins Compromised: {hr['total_user_services']}")
        for idx, s in enumerate(hr["stealers"][:3], 1):
            print(f"\n    Infection #{idx}:")
            print(f"      - Date Compromised : {s['date']}")
            print(f"      - Computer Name    : {YELLOW}{s['computer_name']}{RESET}")
            print(f"      - Operating System : {s['os']}")
            print(f"      - Malware Path     : {s['malware_path']}")
            print(f"      - Stored Passwords : {s['passwords_count']} credential entries")
            if s["sample_logins"]:
                print(f"      - Targeted Logins  : {', '.join(s['sample_logins'][:4])}")
    else:
        print(f"{GREEN}[✓] Stealer Malware : No infostealer infections detected (Hudson Rock Cavalier).{RESET}")

    print("-" * 70)


def render_db_search(query_str: str) -> None:
    print(f"\n{BOLD}[+] LOCAL DATABASE SEARCH: '{CYAN}{query_str}{RESET}'")
    print("-" * 70)
    results = search_local_db(query_str)
    if not results:
        print(f"{YELLOW}[!] No matching records found in local database.{RESET}")
        stats = get_db_stats()
        print(f"    Total records in database: {stats['total_records']:,}")
        print(f"    Import CSV files using: `run.bat indo --db-import path/to/file.csv`")
        print("-" * 70)
        return

    print(f"{GREEN}[✓] Found {len(results)} matching record(s):{RESET}\n")
    for idx, r in enumerate(results, 1):
        print(f"{CYAN}[#{idx}]{RESET} {BOLD}{r['name'] or 'N/A'}{RESET}")
        if r['nik']:
            print(f"    NIK   : {YELLOW}{r['nik']}{RESET}")
        if r['phone']:
            print(f"    Phone : {r['phone']}")
        if r['email']:
            print(f"    Email : {r['email']}")
        if r['plate']:
            print(f"    Plate : {r['plate']}")
        if r['extra']:
            print(f"    Extra : {DIM}{r['extra'][:100]}{'...' if len(r['extra']) > 100 else ''}{RESET}")
        print(f"    Source: {DIM}{r['source_file']}{RESET}")
        print()
    print("-" * 70)


def render_db_import(file_path_str: str) -> None:
    p = Path(file_path_str)
    print(f"\n{BOLD}[+] IMPORTING DATASET INTO LOCAL SECURE DATABASE...{RESET}")
    count, msg = import_csv_file(p)
    if count > 0:
        print(f"{GREEN}[✓] {msg}{RESET}")
    else:
        print(f"{YELLOW}[!] {msg}{RESET}")
    print("-" * 70)


def render_db_stats() -> None:
    stats = get_db_stats()
    print(f"\n{BOLD}[+] LOCAL PRIVATE DATABASE STATUS{RESET}")
    print("-" * 70)
    print(f"    Database File   : {DB_PATH}")
    print(f"    File Size       : {stats['file_size_mb']} MB")
    print(f"    Total Records   : {BOLD}{stats['total_records']:,}{RESET}")
    print(f"    Sources Loaded  : {len(stats['sources'])}")

    if stats['sources']:
        print(f"\n    {'Filename':<35} | {'Records':<10} | {'Imported At'}")
        print("    " + "-" * 62)
        for s in stats['sources']:
            print(f"    {s['filename']:<35} | {s['count']:<10,d} | {s['date']}")

    print(f"\n{CYAN}[*] Quick Tip:{RESET}")
    print(f"    Drop any .csv or .tsv into `{DATA_DIR}` and import with:")
    print(f"    `run.bat indo --db-import path/to/file.csv`")
    print(f"    All data remains 100% offline and is strictly ignored in .gitignore.")
    print("-" * 70)


def interactive_loop() -> None:
    while True:
        print_banner()
        print("  [1] NIK KTP Decoder        - Decode 16-digit NIK (Wilayah, DOB, Gender, Weton)")
        print("  [2] NIP ASN/PNS Decoder    - Decode 18-digit Civil Servant NIP (DOB, TMT CPNS)")
        print("  [3] Phone & E-Wallet Intel - Operator, Area Code, DANA/OVO/GoPay VA & Fraud Dorks")
        print("  [4] Plat Nomor Kendaraan   - Decode Vehicle Plate Region, Type & E-Samsat Portal")
        print("  [5] PDDikti & Court Dorks  - University (Mahasiswa/Dosen), Mahkamah Agung, LPSE & AHU")
        print("  [6] Email Stalker & Bocor  - Live Breaches (XposedOrNot), Stealers & Profiles")
        print("  [7] Local Database Search  - Offline FTS5 search (NIK, Phone, Name, Email, Plat)")
        print("  [8] Import CSV to Local DB - Import private investigation data into SQLite")
        print("  [0] Exit to Master Menu")
        print("=" * 70)
        try:
            choice = input(f"{BOLD}Select tool [0-8]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "0":
            break
        elif choice == "1":
            val = input("\nEnter 16-digit NIK KTP: ").strip()
            if val:
                render_nik(val)
            input("\nPress Enter to continue...")
        elif choice == "2":
            val = input("\nEnter 18-digit NIP ASN/PNS: ").strip()
            if val:
                render_nip(val)
            input("\nPress Enter to continue...")
        elif choice == "3":
            val = input("\nEnter Indonesian Phone Number (e.g. 08123456789): ").strip()
            if val:
                render_phone(val)
            input("\nPress Enter to continue...")
        elif choice == "4":
            val = input("\nEnter License Plate / Plat Nomor (e.g. B 1234 TJD): ").strip()
            if val:
                render_plate(val)
            input("\nPress Enter to continue...")
        elif choice == "5":
            val = input("\nEnter Person Name, University Student, or PT/Company Name: ").strip()
            if val:
                open_ans = input("Open PDDikti & Mahkamah Agung portals in browser? [y/N]: ").strip().lower()
                render_dorks(val, open_browser=(open_ans == "y"))
            input("\nPress Enter to continue...")
        elif choice == "6":
            val = input("\nEnter target Email Address to check for breaches: ").strip()
            if val:
                render_breach(val)
            input("\nPress Enter to continue...")
        elif choice == "7":
            val = input("\nEnter search query (NIK, Name, Phone, Email, Plat): ").strip()
            if val:
                render_db_search(val)
            input("\nPress Enter to continue...")
        elif choice == "8":
            val = input("\nEnter path to CSV / TSV file to import: ").strip().strip('"')
            if val:
                render_db_import(val)
            input("\nPress Enter to continue...")
        else:
            print(f"{RED}Invalid selection.{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indonesian OSINT Intelligence Suite (NIK, NIP ASN, Phone/E-Wallet VA, License Plate, PDDikti, Data Bocor & Local DB)"
    )
    parser.add_argument("--nik", help="Decode a 16-digit Indonesian NIK KTP")
    parser.add_argument("--nip", help="Decode an 18-digit Indonesian NIP (PNS/ASN)")
    parser.add_argument("--phone", help="Analyze an Indonesian phone number & generate E-Wallet VA codes")
    parser.add_argument("--plate", help="Decode an Indonesian vehicle license plate (e.g. 'B 1234 TJD')")
    parser.add_argument("--dorks", help="Generate PDDikti, Mahkamah Agung, LPSE & AHU search dorks for a target")
    parser.add_argument("--open", action="store_true", help="Open primary dork portals in default browser")
    parser.add_argument("--email", "--breach", dest="email", help="Check email for data breaches (XposedOrNot) and stealer malware (Hudson Rock)")
    parser.add_argument("--db-search", help="Search local private offline database (FTS5)")
    parser.add_argument("--db-import", help="Import a CSV/TSV dataset into the local private database")
    parser.add_argument("--db-stats", action="store_true", help="Show statistics of the local private database")

    args = parser.parse_args()

    ran_any = False
    if args.nik:
        render_nik(args.nik)
        ran_any = True
    if args.nip:
        render_nip(args.nip)
        ran_any = True
    if args.phone:
        render_phone(args.phone)
        ran_any = True
    if args.plate:
        render_plate(args.plate)
        ran_any = True
    if args.dorks:
        render_dorks(args.dorks, open_browser=args.open)
        ran_any = True
    if args.email:
        render_breach(args.email)
        ran_any = True
    if args.db_search:
        render_db_search(args.db_search)
        ran_any = True
    if args.db_import:
        render_db_import(args.db_import)
        ran_any = True
    if args.db_stats:
        render_db_stats()
        ran_any = True

    if not ran_any:
        interactive_loop()


if __name__ == "__main__":
    main()
