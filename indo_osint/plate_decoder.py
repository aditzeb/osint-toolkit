"""Indonesian Vehicle License Plate (Plat Nomor / TNKB) Decoder & E-Samsat Locator."""

import re
from typing import Any, Dict

PLATE_REGIONS = {
    # Sumatera
    "BL": ("Aceh (NAD)", "https://esamsat.acehprov.go.id/"),
    "BB": ("Sumatera Utara Bagian Barat (Tapanuli, Nias, Sibolga)", "https://bpprd.sumutprov.go.id/"),
    "BK": ("Sumatera Utara Bagian Timur (Medan, Deli Serdang, Binjai)", "https://bpprd.sumutprov.go.id/"),
    "BA": ("Sumatera Barat (Padang, Bukittinggi, dll.)", "https://bapenda.sumbarprov.go.id/"),
    "BM": ("Riau (Pekanbaru, Dumai, dll.)", "https://badanpendapatan.riau.go.id/"),
    "BP": ("Kepulauan Riau (Batam, Tanjungpinang, Bintan)", "https://bapenda.kepriprov.go.id/"),
    "BG": ("Sumatera Selatan (Palembang, Lubuklinggau, dll.)", "https://bapenda.sumselprov.go.id/"),
    "BN": ("Kepulauan Bangka Belitung", "http://bakuda.babelprov.go.id/"),
    "BE": ("Lampung (Bandar Lampung, Metro, dll.)", "http://pkb.bapenda.lampungprov.go.id/"),
    "BD": ("Bengkulu", "https://bapenda.bengkuluprov.go.id/"),
    "BH": ("Jambi", "http://jambisamsat.net/"),

    # Banten & DKI Jakarta
    "A": ("Banten (Serang, Pandeglang, Cilegon, Lebak, sebagian Kab. Tangerang)", "https://infopkb.bantenprov.go.id/"),
    "B": ("Jadetabek (DKI Jakarta, Depok, Tangerang, Bekasi)", "https://samsat-pkb2.jakarta.go.id/"),

    # Jawa Barat
    "D": ("Bandung Raya (Kota Bandung, Kab. Bandung, Cimahi, Bandung Barat)", "https://bapenda.jabarprov.go.id/infopkb/"),
    "E": ("Eks Karesidenan Cirebon (Cirebon, Indramayu, Majalengka, Kuningan)", "https://bapenda.jabarprov.go.id/infopkb/"),
    "F": ("Bogor, Sukabumi, Cianjur", "https://bapenda.jabarprov.go.id/infopkb/"),
    "T": ("Purwakarta, Karawang, Subang", "https://bapenda.jabarprov.go.id/infopkb/"),
    "Z": ("Garut, Tasikmalaya, Sumedang, Ciamis, Banjar, Pangandaran", "https://bapenda.jabarprov.go.id/infopkb/"),

    # Jawa Tengah & DIY
    "G": ("Eks Karesidenan Pekalongan (Pekalongan, Tegal, Brebes, Batang, Pemalang)", "https://cekpkb.jatengprov.go.id/"),
    "H": ("Eks Karesidenan Semarang (Semarang, Salatiga, Kendal, Demak)", "https://cekpkb.jatengprov.go.id/"),
    "K": ("Eks Karesidenan Pati (Pati, Kudus, Jepara, Rembang, Blora, Grobogan)", "https://cekpkb.jatengprov.go.id/"),
    "R": ("Eks Karesidenan Banyumas (Banyumas/Purwokerto, Cilacap, Purbalingga, Banjarnegara)", "https://cekpkb.jatengprov.go.id/"),
    "AA": ("Eks Karesidenan Kedu (Magelang, Purworejo, Kebumen, Temanggung, Wonosobo)", "https://cekpkb.jatengprov.go.id/"),
    "AD": ("Eks Karesidenan Surakarta (Solo, Sukoharjo, Boyolali, Karanganyar, Wonogiri, Sragen, Klaten)", "https://cekpkb.jatengprov.go.id/"),
    "AB": ("Daerah Istimewa Yogyakarta (Yogyakarta, Sleman, Bantul, Kulon Progo, Gunungkidul)", "https://samsatsleman.jogjaprov.go.id/"),

    # Jawa Timur
    "L": ("Kota Surabaya", "https://info.dipendajatim.go.id/esamsat/"),
    "M": ("Pulau Madura (Bangkalan, Sampang, Pamekasan, Sumenep)", "https://info.dipendajatim.go.id/esamsat/"),
    "W": ("Sidoarjo, Gresik", "https://info.dipendajatim.go.id/esamsat/"),
    "S": ("Bojonegoro, Mojokerto, Tuban, Lamongan, Jombang", "https://info.dipendajatim.go.id/esamsat/"),
    "N": ("Malang, Batu, Pasuruan, Probolinggo, Lumajang", "https://info.dipendajatim.go.id/esamsat/"),
    "P": ("Eks Karesidenan Besuki (Banyuwangi, Jember, Bondowoso, Situbondo)", "https://info.dipendajatim.go.id/esamsat/"),
    "AG": ("Eks Karesidenan Kediri (Kediri, Blitar, Tulungagung, Nganjuk, Trenggalek)", "https://info.dipendajatim.go.id/esamsat/"),
    "AE": ("Eks Karesidenan Madiun (Madiun, Ngawi, Magetan, Ponorogo, Pacitan)", "https://info.dipendajatim.go.id/esamsat/"),

    # Bali & Nusa Tenggara
    "DK": ("Bali (Denpasar, Badung, Gianyar, Buleleng, dll.)", "https://portal.bpdbali.id/infosamsat/"),
    "DR": ("NTB - Pulau Lombok (Mataram, Lombok Barat/Tengah/Timur/Utara)", "https://esamsat.ntbprov.go.id/"),
    "EA": ("NTB - Pulau Sumbawa (Sumbawa, Dompu, Bima)", "https://esamsat.ntbprov.go.id/"),
    "DH": ("NTT - Pulau Timor (Kupang, TTS, TTU, Belu, Rote Ndao)", "http://bapenda.nttprov.go.id/"),
    "EB": ("NTT - Pulau Flores & Alor (Ende, Sikka, Manggarai, Ngada, Alor)", "http://bapenda.nttprov.go.id/"),
    "ED": ("NTT - Pulau Sumba (Sumba Barat, Sumba Timur, dll.)", "http://bapenda.nttprov.go.id/"),

    # Kalimantan
    "KB": ("Kalimantan Barat (Pontianak, Singkawang, dll.)", "https://bapenda.kalbarprov.go.id/"),
    "KH": ("Kalimantan Tengah (Palangka Raya, Sampit, dll.)", "https://bapenda.kalteng.go.id/"),
    "DA": ("Kalimantan Selatan (Banjarmasin, Banjarbaru, dll.)", "https://bapenda.kalselprov.go.id/"),
    "KT": ("Kalimantan Timur (Samarinda, Balikpapan, Bontang, Kukar)", "http://simpator.kaltimprov.go.id/"),
    "KU": ("Kalimantan Utara (Tarakan, Bulungan, Nunukan)", "https://bapenda.kaltaraprov.go.id/"),

    # Sulawesi
    "DB": ("Sulawesi Utara Daratan (Manado, Tomohon, Bitung, Minahasa, Bolmong)", "https://bapenda.sulutprov.go.id/"),
    "DL": ("Sulawesi Utara Kepulauan (Sangihe, Talaud, Sitaro)", "https://bapenda.sulutprov.go.id/"),
    "DM": ("Gorontalo", "https://bapenda.gorontaloprov.go.id/"),
    "DN": ("Sulawesi Tengah (Palu, Poso, Luwuk, Morowali)", "https://bapenda.sultengprov.go.id/"),
    "DC": ("Sulawesi Barat (Mamuju, Majene, Polewali Mandar)", "https://bapenda.sulbarprov.go.id/"),
    "DD": ("Sulawesi Selatan Bagian Selatan (Makassar, Gowa, Maros, Bulukumba)", "https://bapenda.sulselprov.go.id/"),
    "DP": ("Sulawesi Selatan Bagian Utara (Parepare, Palopo, Bone, Toraja, Luwu)", "https://bapenda.sulselprov.go.id/"),
    "DW": ("Sulawesi Selatan Bagian Tengah (Bone, Wajo, Soppeng, Sinjai)", "https://bapenda.sulselprov.go.id/"),
    "DT": ("Sulawesi Tenggara (Kendari, Baubau, Kolaka, Konawe)", "https://bapenda.sultraprov.go.id/"),

    # Maluku & Papua
    "DE": ("Maluku (Ambon, Tual, Maluku Tengah)", "https://bapenda.malukuprov.go.id/"),
    "DG": ("Maluku Utara (Ternate, Tidore, Halmahera)", "https://bapenda.malutprov.go.id/"),
    "PA": ("Papua (Jayapura, Biak, Yapen, Sarmi)", "https://bapenda.papua.go.id/"),
    "PB": ("Papua Barat (Manokwari, Fakfak, Kaimana)", "https://bapenda.papuabaratprov.go.id/"),
    "PS": ("Papua Selatan (Merauke, Boven Digoel, Mappi, Asmat)", "https://bapenda.papua.go.id/"),
    "PT": ("Papua Tengah (Nabire, Mimika/Timika, Paniai)", "https://bapenda.papua.go.id/"),
    "PG": ("Papua Pegunungan (Jayawijaya/Wamena, Lanny Jaya, Tolikara)", "https://bapenda.papua.go.id/"),
    "PY": ("Papua Barat Daya (Kota Sorong, Kab. Sorong, Raja Ampat)", "https://bapenda.papuabaratprov.go.id/"),

    # Special Plates
    "RI": ("Pejabat Tinggi Negara Republik Indonesia (State Officials)", "https://setneg.go.id/"),
    "CD": ("Corps Diplomatique (Foreign Diplomatic Mission)", "https://kemlu.go.id/"),
    "CC": ("Corps Consulaire (Foreign Consular Mission)", "https://kemlu.go.id/"),
}

# Jadetabek (B Plate) 1st Suffix Letter -> Sub-Region / Polres Jurisdiction
B_SUBREGION_MAP = {
    "B": "Kota Administrasi Jakarta Barat",
    "C": "Kota Tangerang (Banten)",
    "E": "Kota Depok (Jawa Barat)",
    "F": "Kabupaten Bekasi (Cikarang - Jawa Barat)",
    "G": "Kabupaten Tangerang (Tigaraksa - Banten)",
    "K": "Kota Bekasi (Jawa Barat)",
    "N": "Kabupaten Tangerang / Tangerang Selatan (Banten)",
    "P": "Kota Administrasi Jakarta Pusat",
    "S": "Kota Administrasi Jakarta Selatan",
    "T": "Kota Administrasi Jakarta Timur",
    "U": "Kota Administrasi Jakarta Utara",
    "V": "Kota Tangerang Selatan (Serpong/BSD - Banten)",
    "W": "Kota Tangerang Selatan (Banten)",
    "Z": "Kota Depok (Cinere/Sawangan - Jawa Barat)",
}

# Jadetabek (B Plate) 2nd Suffix Letter -> Vehicle Body Classification
B_VEHICLE_TYPE_MAP = {
    "A": "Sedan / Hatchback",
    "B": "Minibus / SUV / MPV (Penumpang)",
    "C": "Pick-up / Single Cabin / Truk Kecil",
    "D": "Minibus / MPV / Microbus",
    "E": "Minibus / SUV",
    "F": "Minibus / MPV (Penumpang)",
    "G": "Minibus / Kendaraan Penumpang",
    "J": "Jeep / SUV / Crossover",
    "K": "Kendaraan Penumpang / Minibus",
    "P": "Bus / Kendaraan Penumpang Besar",
    "Q": "Kendaraan Staf / Operasional Pemerintah",
    "R": "Minibus / Kendaraan Penumpang",
    "S": "Sedan / Minibus",
    "T": "Taksi / Angkutan Umum",
    "U": "Kendaraan Operasional Pemerintah / Korps",
    "V": "Minibus / MPV",
    "X": "Kendaraan Khusus / Minibus",
    "Y": "Minibus / Kendaraan Penumpang",
    "Z": "Minibus / Kendaraan Penumpang",
}


def decode_plate(raw_plate: str) -> Dict[str, Any]:
    """Parse an Indonesian license plate (e.g. 'B 1234 TJD') and extract regional/vehicle metadata."""
    cleaned = raw_plate.strip().upper()
    m = re.match(r"^([A-Z]{1,2})\s*(\d{1,4})\s*([A-Z]{0,3})$", cleaned)
    if not m:
        return {
            "input": raw_plate,
            "valid": False,
            "error": "Format plat nomor tidak dikenali. Contoh format valid: 'B 1234 TJD', 'D 4567 ABC', 'DK 8888 XY'.",
        }

    prefix, num_str, suffix = m.group(1), m.group(2), m.group(3)
    num = int(num_str)

    region_info = PLATE_REGIONS.get(prefix)
    region_name = region_info[0] if region_info else f"Unknown Region Code ({prefix})"
    samsat_url = region_info[1] if region_info else "https://signal.korlantas.polri.go.id/"

    # Number range classification (standard Korlantas Polri allocation for DKI / Major Cities)
    if 1 <= num <= 2999:
        num_category = "Kendaraan Penumpang (Passenger Car / Sedan / SUV / MPV)"
    elif 3000 <= num <= 6999:
        num_category = "Sepeda Motor (Motorcycle)"
    elif 7000 <= num <= 7999:
        num_category = "Bus (Passenger Bus)"
    elif 8000 <= num <= 8999:
        num_category = "Kendaraan Beban / Truk / Pick-up (Cargo / Truck)"
    elif 9000 <= num <= 9999:
        num_category = "Kendaraan Beban Berat / Khusus / Trailer (Heavy Duty / Special)"
    else:
        num_category = "Unclassified"

    sub_region = "Sesuai Samsat Wilayah"
    body_type = num_category

    if prefix == "B" and suffix:
        first_char = suffix[0]
        sub_region = B_SUBREGION_MAP.get(first_char, f"Jadetabek (Sub-code '{first_char}')")
        if len(suffix) >= 2 and (1 <= num <= 2999 or 7000 <= num <= 9999):
            second_char = suffix[1]
            body_type = B_VEHICLE_TYPE_MAP.get(second_char, num_category)

    return {
        "input": raw_plate,
        "formatted_plate": f"{prefix} {num} {suffix}".strip(),
        "valid": region_info is not None,
        "prefix": prefix,
        "number": num,
        "suffix": suffix or "(Tanpa Seri Akhir)",
        "region": region_name,
        "sub_region_samsat": sub_region,
        "number_allocation_class": num_category,
        "specific_vehicle_type": body_type,
        "samsat_portal": samsat_url,
        "national_app": "SIGNAL (Samsat Digital Nasional) - https://signal.korlantas.polri.go.id/",
    }
