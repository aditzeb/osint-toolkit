"""Indonesian Public Registry Dorks (PDDikti, Mahkamah Agung, AHU, LPSE) & 18-Digit NIP (ASN/PNS) Decoder."""

import datetime
from typing import Any, Dict
import urllib.parse


def parse_nip_asn(raw_nip: str) -> Dict[str, Any]:
    """
    Decode an 18-digit Indonesian NIP (Nomor Induk Pegawai - PNS / ASN).
    Format: YYYYMMDD (Birthdate) + YYYYMM (CPNS Appointment) + G (1=Male, 2=Female) + XXX (Sequence)
    """
    digits = "".join(ch for ch in raw_nip.strip() if ch.isdigit())
    res: Dict[str, Any] = {
        "input": raw_nip,
        "cleaned_nip": digits,
        "valid": False,
        "errors": [],
    }

    if len(digits) != 18:
        res["errors"].append(f"NIP ASN/PNS must be 18 digits (got {len(digits)} digits).")
        return res

    b_year = int(digits[0:4])
    b_month = int(digits[4:6])
    b_day = int(digits[6:8])

    tmt_year = int(digits[8:12])
    tmt_month = int(digits[12:14])

    gender_code = digits[14]
    seq = digits[15:18]

    try:
        b_date = datetime.date(b_year, b_month, b_day)
        today = datetime.date.today()
        age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
        res["birthdate"] = b_date.strftime("%d %B %Y")
        res["age"] = f"{age} years old"
        res["retirement_year_est"] = b_year + 58  # Standard 58 BUP for Administrative ASN (60-65 for functional)
    except ValueError as exc:
        res["errors"].append(f"Invalid birth date in NIP ({b_day:02d}-{b_month:02d}-{b_year}): {exc}")

    if not (1970 <= tmt_year <= datetime.date.today().year + 1 and 1 <= tmt_month <= 12):
        res["errors"].append(f"Invalid CPNS appointment year/month ({tmt_year}-{tmt_month:02d}).")
    else:
        tmt_date = datetime.date(tmt_year, tmt_month, 1)
        years_service = datetime.date.today().year - tmt_year
        res["cpns_appointment"] = tmt_date.strftime("%B %Y")
        res["years_of_service"] = f"~{years_service} years"
        if "birthdate" in res:
            res["age_at_appointment"] = f"{tmt_year - b_year} years old"

    if gender_code == "1":
        res["gender"] = "Laki-laki (Male)"
    elif gender_code == "2":
        res["gender"] = "Perempuan (Female)"
    else:
        res["gender"] = f"Unknown ({gender_code})"
        res["errors"].append(f"Invalid gender digit '{gender_code}' (must be 1 or 2).")

    res["sequence"] = seq
    res["valid"] = len(res["errors"]) == 0
    return res


def generate_indo_dorks(target_query: str) -> Dict[str, Dict[str, str]]:
    """Generate targeted Indonesian OSINT lookup URLs and search dorks for a person, handle, or company."""
    q_raw = target_query.strip()
    q_exact = urllib.parse.quote(f'"{q_raw}"')
    q_path = urllib.parse.quote(q_raw)

    dorks = {
        "Education & Academic (PDDikti & Kampus)": {
            "PDDikti Kemdiktisaintek Portal": f"https://pddikti.kemdiktisaintek.go.id/search/all/{q_path}",
            "Google PDDikti Profile Dork": f"https://www.google.com/search?q={q_exact}+site:pddikti.kemdiktisaintek.go.id+OR+site:pddikti.kemdikbud.go.id",
            "University Thesis / Repository (.ac.id)": f"https://www.google.com/search?q={q_exact}+site:.ac.id+(filetype:pdf+OR+skripsi+OR+tesis+OR+mahasiswa+OR+dosen)",
            "SINTA / Garuda Researcher Profile": f"https://www.google.com/search?q={q_exact}+(site:sinta.kemdikbud.go.id+OR+site:garuda.kemdikbud.go.id)",
        },
        "Legal & Court Records (Mahkamah Agung & SIPP)": {
            "Direktori Putusan Mahkamah Agung": f"https://www.google.com/search?q={q_exact}+site:putusan3.mahkamahagung.go.id",
            "SIPP Pengadilan Negeri / Agama": f"https://www.google.com/search?q={q_exact}+inurl:sipp.pn+OR+inurl:sipp.pa",
            "KPK / LHKPN Public Officials Wealth": f"https://www.google.com/search?q={q_exact}+site:kpk.go.id+OR+LHKPN",
        },
        "Corporate, Procurement & Government (.go.id)": {
            "LPSE Government Tender / Vendor": f"https://www.google.com/search?q={q_exact}+inurl:lpse+OR+site:inaproc.id",
            "AHU Kemenkumham Corporate Dork": f"https://www.google.com/search?q={q_exact}+(site:ahu.go.id+OR+\"Direktur\"+OR+\"Komisaris\"+OR+\"Akta\")",
            "Official Government Documents (.go.id PDF/XLSX)": f"https://www.google.com/search?q={q_exact}+site:.go.id+(filetype:pdf+OR+filetype:xlsx+OR+filetype:doc)",
            "PSE Kominfo Registered Portals": "https://pse.kominfo.go.id/",
        },
        "Indonesian Social, Forum & E-Commerce": {
            "Kaskus / Indonesian Forums": f"https://www.google.com/search?q={q_exact}+(site:kaskus.co.id+OR+site:kompasiana.com+OR+site:quora.com)",
            "Tokopedia / Shopee / Bukalapak Store": f"https://www.google.com/search?q={q_exact}+(site:tokopedia.com+OR+site:shopee.co.id+OR+site:bukalapak.com)",
            "LinkedIn Indonesia Profile": f"https://www.google.com/search?q={q_exact}+site:id.linkedin.com/in/+OR+site:linkedin.com/in/",
        },
    }
    return dorks
