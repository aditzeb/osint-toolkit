"""Indonesian 16-Digit NIK (Nomor Induk Kependudukan) Decoder & Validator."""

import datetime
import json
import urllib.request
from typing import Any, Dict, Optional

from .wilayah_data import KABUPATEN_KOTA, PROVINCES

DAYS_ID = [
    "Senin (Monday)",
    "Selasa (Tuesday)",
    "Rabu (Wednesday)",
    "Kamis (Thursday)",
    "Jumat (Friday)",
    "Sabtu (Saturday)",
    "Minggu (Sunday)",
]

# Javanese Pasaran cycle (5-day cycle); reference anchor: 1970-01-01 was Kamis Wage (index 3)
PASARAN_JAWA = ["Legi", "Pahing", "Pon", "Wage", "Kliwon"]


def get_zodiac(day: int, month: int) -> str:
    zodiacs = [
        (120, "Capricorn"), (218, "Aquarius"), (320, "Pisces"), (420, "Aries"),
        (521, "Taurus"), (621, "Gemini"), (722, "Cancer"), (823, "Leo"),
        (923, "Virgo"), (1023, "Libra"), (1122, "Scorpio"), (1222, "Sagittarius"),
        (1231, "Capricorn"),
    ]
    md = month * 100 + day
    for cutoff, name in zodiacs:
        if md <= cutoff:
            return name
    return "Capricorn"


def get_generation(year: int) -> str:
    if year >= 2013:
        return "Gen Alpha"
    if year >= 1997:
        return "Gen Z"
    if year >= 1981:
        return "Millennial (Gen Y)"
    if year >= 1965:
        return "Gen X"
    if year >= 1946:
        return "Baby Boomer"
    return "Silent Generation"


def fetch_kecamatan_name(kab_code: str, kec_code: str) -> Optional[str]:
    """Attempt to resolve exact Kecamatan name from Kemendagri Dukcapil dataset (wilayah.id)."""
    dotted_kab = f"{kab_code[:2]}.{kab_code[2:4]}"
    dotted_kec = f"{dotted_kab}.{kec_code}"
    url = f"https://wilayah.id/api/districts/{dotted_kab}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            for item in payload.get("data", []):
                if item.get("code") == dotted_kec:
                    return item.get("name", "")
    except Exception:
        pass
    return None


def parse_nik(nik_raw: str, online_lookup: bool = True) -> Dict[str, Any]:
    """Parse and validate a 16-digit Indonesian NIK."""
    nik = "".join(ch for ch in nik_raw.strip() if ch.isdigit())
    result: Dict[str, Any] = {
        "input": nik_raw,
        "cleaned_nik": nik,
        "valid": False,
        "errors": [],
        "warnings": [],
    }

    if len(nik) != 16:
        result["errors"].append(f"NIK must be exactly 16 digits (got {len(nik)} digits).")
        return result

    prov_code = nik[0:2]
    kab_code = nik[0:4]
    kec_sub = nik[4:6]
    full_kec_code = f"{prov_code}.{nik[2:4]}.{kec_sub}"

    raw_day = int(nik[6:8])
    month = int(nik[8:10])
    year_2d = int(nik[10:12])
    seq = nik[12:16]

    province_name = PROVINCES.get(prov_code)
    if not province_name:
        result["errors"].append(f"Unknown Province code '{prov_code}'.")

    kab_name = KABUPATEN_KOTA.get(kab_code)
    if not kab_name:
        result["warnings"].append(
            f"Kabupaten/Kota code '{prov_code}.{nik[2:4]}' not in standard table (may be newly split regency)."
        )
        kab_name = f"Unknown Regency/City ({prov_code}.{nik[2:4]})"

    # Gender & Birth Day
    if 1 <= raw_day <= 31:
        gender = "Laki-laki (Male)"
        day = raw_day
    elif 41 <= raw_day <= 71:
        gender = "Perempuan (Female)"
        day = raw_day - 40
    else:
        gender = "Invalid"
        day = raw_day
        result["errors"].append(f"Invalid birth day encoding '{raw_day:02d}' (must be 01-31 for Male or 41-71 for Female).")

    # Birth Year resolution
    current_year = datetime.date.today().year
    curr_2d = current_year % 100
    full_year = (2000 + year_2d) if year_2d <= curr_2d else (1900 + year_2d)

    birth_date_obj: Optional[datetime.date] = None
    try:
        birth_date_obj = datetime.date(full_year, month, day)
    except ValueError as exc:
        result["errors"].append(f"Invalid calendar date ({day:02d}-{month:02d}-{full_year}): {exc}")

    if seq == "0000":
        result["warnings"].append("Sequence number is '0000' (standard Dukcapil sequence starts at 0001).")

    kec_name = None
    if online_lookup and province_name:
        kec_name = fetch_kecamatan_name(kab_code, kec_sub)

    result["valid"] = len(result["errors"]) == 0
    result["province_code"] = prov_code
    result["province_name"] = province_name or "Unknown"
    result["kabupaten_code"] = f"{prov_code}.{nik[2:4]}"
    result["kabupaten_name"] = kab_name
    result["kecamatan_code"] = full_kec_code
    result["kecamatan_name"] = kec_name or f"District #{kec_sub} (Code: {full_kec_code})"
    result["gender"] = gender
    result["sequence"] = seq

    if birth_date_obj:
        today = datetime.date.today()
        age = today.year - birth_date_obj.year - (
            (today.month, today.day) < (birth_date_obj.month, birth_date_obj.day)
        )
        # Pasaran Jawa calculation from 1970-01-01 (Kamis Wage, index 3)
        delta_days = (birth_date_obj - datetime.date(1970, 1, 1)).days
        pasaran = PASARAN_JAWA[(3 + delta_days) % 5]
        day_name = DAYS_ID[birth_date_obj.weekday()]

        result["birthdate"] = birth_date_obj.strftime("%d %B %Y")
        result["birthdate_iso"] = birth_date_obj.isoformat()
        result["age"] = f"{age} years old"
        result["day_of_week"] = day_name
        result["weton_jawa"] = f"{day_name.split()[0]} {pasaran}"
        result["zodiac"] = get_zodiac(day, month)
        result["generation"] = get_generation(full_year)
    else:
        result["birthdate"] = f"{day:02d}-{month:02d}-{full_year} (Invalid)"
        result["age"] = "N/A"
        result["day_of_week"] = "N/A"
        result["weton_jawa"] = "N/A"
        result["zodiac"] = "N/A"
        result["generation"] = "N/A"

    result["verification_links"] = {
        "KPU DPT Voter Check": "https://cekdptonline.kpu.go.id/",
        "BPJS Kesehatan / JKN": "https://daftar.bpjs-kesehatan.go.id/",
        "DJP NPWP Check": "https://ereg.pajak.go.id/ceknpwp",
    }

    return result
