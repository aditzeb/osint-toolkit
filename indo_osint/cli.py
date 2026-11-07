#!/usr/bin/env python3
"""Interactive & CLI Runner for the Indonesian OSINT Intelligence Suite."""

import argparse
import os
import sys
import webbrowser

# Ensure parent directory is importable when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indo_osint.nik_parser import parse_nik
from indo_osint.phone_intel import analyze_indo_phone
from indo_osint.plate_decoder import decode_plate
from indo_osint.registry_dorks import generate_indo_dorks, parse_nip_asn

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
    print(f"{DIM}   NIK KTP | NIP ASN | Telco & E-Wallet VA | Plat Nomor | PDDikti     {RESET}")
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


def interactive_loop() -> None:
    while True:
        print_banner()
        print("  [1] NIK KTP Decoder        - Decode 16-digit NIK (Wilayah, DOB, Gender, Weton)")
        print("  [2] NIP ASN/PNS Decoder    - Decode 18-digit Civil Servant NIP (DOB, TMT CPNS)")
        print("  [3] Phone & E-Wallet Intel - Operator, Area Code, DANA/OVO/GoPay VA & Fraud Dorks")
        print("  [4] Plat Nomor Kendaraan   - Decode Vehicle Plate Region, Type & E-Samsat Portal")
        print("  [5] PDDikti & Court Dorks  - University (Mahasiswa/Dosen), Mahkamah Agung, LPSE & AHU")
        print("  [0] Exit to Master Menu")
        print("=" * 70)
        try:
            choice = input(f"{BOLD}Select tool [0-5]: {RESET}").strip()
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
        else:
            print(f"{RED}Invalid selection.{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indonesian OSINT Intelligence Suite (NIK, NIP ASN, Phone/E-Wallet VA, License Plate, PDDikti & Court Dorks)"
    )
    parser.add_argument("--nik", help="Decode a 16-digit Indonesian NIK KTP")
    parser.add_argument("--nip", help="Decode an 18-digit Indonesian NIP (PNS/ASN)")
    parser.add_argument("--phone", help="Analyze an Indonesian phone number & generate E-Wallet VA codes")
    parser.add_argument("--plate", help="Decode an Indonesian vehicle license plate (e.g. 'B 1234 TJD')")
    parser.add_argument("--dorks", help="Generate PDDikti, Mahkamah Agung, LPSE & AHU search dorks for a target")
    parser.add_argument("--open", action="store_true", help="Open primary dork portals in default browser")

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

    if not ran_any:
        interactive_loop()


if __name__ == "__main__":
    main()
