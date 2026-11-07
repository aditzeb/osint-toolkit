"""Indonesian Phone Number Carrier Prefix, Landline Area Code & E-Wallet VA OSINT Module."""

from typing import Any, Dict
import urllib.parse

# Indonesian Mobile Operator Prefixes (4-digit 08xx format)
MOBILE_PREFIXES = {
    # Telkomsel
    "0811": ("PT Telekomunikasi Selular (Telkomsel)", "Kartu Halo", "Postpaid (Pascabayar)"),
    "0812": ("PT Telekomunikasi Selular (Telkomsel)", "Telkomsel PraBayar (Simpati)", "Prepaid / Postpaid"),
    "0813": ("PT Telekomunikasi Selular (Telkomsel)", "Telkomsel PraBayar (Simpati)", "Prepaid / Postpaid"),
    "0821": ("PT Telekomunikasi Selular (Telkomsel)", "Telkomsel PraBayar (Simpati)", "Prepaid"),
    "0822": ("PT Telekomunikasi Selular (Telkomsel)", "Telkomsel PraBayar (Loop / Simpati)", "Prepaid"),
    "0823": ("PT Telekomunikasi Selular (Telkomsel)", "Telkomsel PraBayar (Kartu AS)", "Prepaid"),
    "0851": ("PT Telekomunikasi Selular (Telkomsel)", "by.U / Kartu AS", "Digital Prepaid"),
    "0852": ("PT Telekomunikasi Selular (Telkomsel)", "Telkomsel PraBayar (Kartu AS)", "Prepaid"),
    "0853": ("PT Telekomunikasi Selular (Telkomsel)", "Telkomsel PraBayar (Kartu AS)", "Prepaid"),

    # Indosat Ooredoo Hutchison (IOH)
    "0814": ("PT Indosat Tbk (Indosat Ooredoo Hutchison)", "Indosat M2 Broadband", "Data / Broadband"),
    "0815": ("PT Indosat Tbk (Indosat Ooredoo Hutchison)", "IM3 / Mentari / Matrix", "Prepaid / Postpaid"),
    "0816": ("PT Indosat Tbk (Indosat Ooredoo Hutchison)", "IM3 / Mentari / Matrix", "Prepaid / Postpaid"),
    "0855": ("PT Indosat Tbk (Indosat Ooredoo Hutchison)", "IM3 Postpaid (Matrix)", "Postpaid (Pascabayar)"),
    "0856": ("PT Indosat Tbk (Indosat Ooredoo Hutchison)", "IM3", "Prepaid"),
    "0857": ("PT Indosat Tbk (Indosat Ooredoo Hutchison)", "IM3", "Prepaid"),
    "0858": ("PT Indosat Tbk (Indosat Ooredoo Hutchison)", "IM3 / Mentari", "Prepaid"),

    # Tri (3) - Now part of Indosat Ooredoo Hutchison
    "0895": ("PT Indosat Tbk (Tri / 3 Indonesia)", "Tri (3)", "Prepaid"),
    "0896": ("PT Indosat Tbk (Tri / 3 Indonesia)", "Tri (3)", "Prepaid"),
    "0897": ("PT Indosat Tbk (Tri / 3 Indonesia)", "Tri (3)", "Prepaid"),
    "0898": ("PT Indosat Tbk (Tri / 3 Indonesia)", "Tri (3)", "Prepaid"),
    "0899": ("PT Indosat Tbk (Tri / 3 Indonesia)", "Tri (3)", "Prepaid"),

    # XL Axiata
    "0817": ("PT XL Axiata Tbk", "XL PraBayar / XL Prioritas", "Prepaid / Postpaid"),
    "0818": ("PT XL Axiata Tbk", "XL PraBayar / XL Prioritas", "Prepaid / Postpaid"),
    "0819": ("PT XL Axiata Tbk", "XL PraBayar / XL Prioritas", "Prepaid / Postpaid"),
    "0859": ("PT XL Axiata Tbk", "XL PraBayar / Live.On", "Prepaid / Digital"),
    "0877": ("PT XL Axiata Tbk", "XL PraBayar", "Prepaid"),
    "0878": ("PT XL Axiata Tbk", "XL PraBayar / Live.On", "Prepaid"),

    # AXIS (XL Axiata)
    "0831": ("PT XL Axiata Tbk (AXIS)", "AXIS", "Prepaid"),
    "0832": ("PT XL Axiata Tbk (AXIS)", "AXIS", "Prepaid"),
    "0833": ("PT XL Axiata Tbk (AXIS)", "AXIS", "Prepaid"),
    "0838": ("PT XL Axiata Tbk (AXIS)", "AXIS", "Prepaid"),

    # Smartfren
    "0881": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid / Postpaid"),
    "0882": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid / Postpaid"),
    "0883": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid"),
    "0884": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid"),
    "0885": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid"),
    "0886": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid"),
    "0887": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid"),
    "0888": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid / Postpaid"),
    "0889": ("PT Smartfren Telecom Tbk", "Smartfren", "Prepaid"),
}

# Major Indonesian PSTN / Landline Area Codes
LANDLINE_AREA_CODES = {
    "021": "Jabodetabek (DKI Jakarta, Tangerang, Bekasi, Depok)",
    "022": "Bandung, Cimahi, Sumedang (Jawa Barat)",
    "024": "Semarang, Demak (Jawa Tengah)",
    "0251": "Bogor (Jawa Barat)",
    "0254": "Serang, Cilegon, Merak (Banten)",
    "0260": "Subang (Jawa Barat)",
    "0261": "Sumedang (Jawa Barat)",
    "0262": "Garut (Jawa Barat)",
    "0263": "Cianjur (Jawa Barat)",
    "0264": "Purwakarta, Cikampek (Jawa Barat)",
    "0265": "Tasikmalaya, Ciamis, Banjar (Jawa Barat)",
    "0266": "Sukabumi (Jawa Barat)",
    "0267": "Karawang (Jawa Barat)",
    "0231": "Cirebon (Jawa Barat)",
    "0271": "Surakarta (Solo), Sukoharjo, Karanganyar, Boyolali, Sragen, Klaten",
    "0274": "DI Yogyakarta (Yogyakarta, Sleman, Bantul, Gunungkidul, Kulon Progo)",
    "0281": "Purwokerto, Banyumas, Purbalingga (Jawa Tengah)",
    "0285": "Pekalongan, Batang (Jawa Tengah)",
    "0291": "Kudus, Jepara, Demak (Jawa Tengah)",
    "0293": "Magelang, Temanggung (Jawa Tengah)",
    "031": "Surabaya, Gresik, Sidoarjo, Bangkalan (Jawa Timur)",
    "0321": "Mojokerto, Jombang (Jawa Timur)",
    "0331": "Jember (Jawa Timur)",
    "0333": "Banyuwangi (Jawa Timur)",
    "0341": "Malang, Batu (Jawa Timur)",
    "0342": "Blitar (Jawa Timur)",
    "0343": "Pasuruan (Jawa Timur)",
    "0351": "Madiun, Magetan, Ngawi, Ponorogo (Jawa Timur)",
    "0354": "Kediri (Jawa Timur)",
    "0361": "Denpasar, Badung, Gianyar, Tabanan (Bali)",
    "0362": "Singaraja, Buleleng (Bali)",
    "0370": "Mataram, Lombok (NTB)",
    "0380": "Kupang (NTT)",
    "0411": "Makassar, Maros, Gowa (Sulawesi Selatan)",
    "0431": "Manado, Tomohon, Minahasa (Sulawesi Utara)",
    "0451": "Palu (Sulawesi Tengah)",
    "0401": "Kendari (Sulawesi Tenggara)",
    "0511": "Banjarmasin, Banjarbaru, Martapura (Kalimantan Selatan)",
    "0536": "Palangka Raya (Kalimantan Tengah)",
    "0541": "Samarinda, Tenggarong (Kalimantan Timur)",
    "0542": "Balikpapan (Kalimantan Timur)",
    "0561": "Pontianak, Kubu Raya (Kalimantan Barat)",
    "061": "Medan, Binjai, Deli Serdang (Sumatera Utara)",
    "0622": "Pematangsiantar (Sumatera Utara)",
    "0651": "Banda Aceh, Aceh Besar (Aceh)",
    "0711": "Palembang, Banyuasin, Ogan Ilir (Sumatera Selatan)",
    "0721": "Bandar Lampung (Lampung)",
    "0736": "Bengkulu",
    "0741": "Jambi",
    "0751": "Padang, Pariaman (Sumatera Barat)",
    "0752": "Bukittinggi, Payakumbuh, Padang Panjang (Sumatera Barat)",
    "0761": "Pekanbaru, Siak (Riau)",
    "0771": "Tanjungpinang, Bintan (Kepulauan Riau)",
    "0778": "Batam (Kepulauan Riau)",
    "0911": "Ambon (Maluku)",
    "0921": "Ternate (Maluku Utara)",
    "0951": "Sorong (Papua Barat Daya)",
    "0967": "Jayapura (Papua)",
}


def analyze_indo_phone(raw_phone: str) -> Dict[str, Any]:
    """Normalize and extract Indonesian intelligence from a phone number."""
    digits = "".join(ch for ch in raw_phone.strip() if ch.isdigit())
    if digits.startswith("62"):
        local_num = "0" + digits[2:]
        intl_num = "+" + digits
        wa_num = digits
    elif digits.startswith("0"):
        local_num = digits
        intl_num = "+62" + digits[1:]
        wa_num = "62" + digits[1:]
    elif digits.startswith("8"):
        local_num = "0" + digits
        intl_num = "+62" + digits
        wa_num = "62" + digits
    else:
        local_num = digits
        intl_num = "+" + digits
        wa_num = digits

    result: Dict[str, Any] = {
        "input": raw_phone,
        "local_format": local_num,
        "international_format": intl_num,
        "whatsapp_id": f"{wa_num}@s.whatsapp.net",
        "valid_length": 10 <= len(local_num) <= 13,
        "type": "Unknown",
        "operator": "Unknown",
        "brand": "Unknown",
        "billing_model": "Unknown",
        "region": "National (Indonesia)",
    }

    if local_num.startswith("08"):
        result["type"] = "Mobile / Cellular (Seluler)"
        prefix4 = local_num[:4]
        info = MOBILE_PREFIXES.get(prefix4)
        if info:
            result["operator"], result["brand"], result["billing_model"] = info
        result["prefix"] = prefix4
    else:
        # Check 4-digit then 3-digit landline area code
        area4 = local_num[:4]
        area3 = local_num[:3]
        if area4 in LANDLINE_AREA_CODES:
            result["type"] = "Fixed Line / Landline (PSTN)"
            result["operator"] = "PT Telkom Indonesia / Fixed PSTN"
            result["brand"] = f"Area Code {area4}"
            result["region"] = LANDLINE_AREA_CODES[area4]
        elif area3 in LANDLINE_AREA_CODES:
            result["type"] = "Fixed Line / Landline (PSTN)"
            result["operator"] = "PT Telkom Indonesia / Fixed PSTN"
            result["brand"] = f"Area Code {area3}"
            result["region"] = LANDLINE_AREA_CODES[area3]

    # E-Wallet Virtual Account (VA) Name Resolution Codes
    # (Used by Indonesian investigators to check registered real names via M-Banking inquiry before confirming transfer)
    if local_num.startswith("08"):
        result["ewallet_va_inquiry_codes"] = {
            "DANA (via BCA VA)": f"3901{local_num}",
            "DANA (via Mandiri VA)": f"89508{local_num}",
            "DANA (via BRI VA)": f"88810{local_num}",
            "OVO (via BCA VA)": f"39358{local_num}",
            "OVO (via Mandiri VA)": f"60001{local_num}",
            "GoPay (via BCA VA)": f"70001{local_num}",
            "GoPay (via Mandiri VA)": f"60737{local_num}",
            "GoPay (via BRI VA)": f"301341{local_num}",
            "ShopeePay (via BCA VA)": f"893{local_num}",
            "ShopeePay (via Mandiri VA)": f"89308{local_num}",
            "LinkAja (via BCA VA)": f"09110{local_num}",
        }
    else:
        result["ewallet_va_inquiry_codes"] = {}

    q_both = urllib.parse.quote(f'"{local_num}" OR "{intl_num}" OR "{wa_num}"')
    q_fraud = urllib.parse.quote(f'("{local_num}" OR "{intl_num}") AND ("penipu" OR "scam" OR "kronologi" OR "hati-hati")')
    q_market = urllib.parse.quote(
        f'("{local_num}" OR "{intl_num}") (site:tokopedia.com OR site:shopee.co.id OR site:kaskus.co.id OR site:olx.co.id OR site:facebook.com)'
    )
    q_docs = urllib.parse.quote(f'("{local_num}" OR "{intl_num}") site:.go.id OR site:.ac.id OR filetype:pdf OR filetype:xlsx')

    result["osint_links"] = {
        "WhatsApp Direct Chat": f"https://wa.me/{wa_num}",
        "Truecaller Indonesia Search": f"https://www.truecaller.com/search/id/{local_num}",
        "Getcontact Web Portal": "https://web.getcontact.com/",
        "Kominfo CekRekening.id": "https://cekrekening.id/",
        "Kredibel Fraud Database": "https://www.kredibel.co.id/",
        "Google General Mention Dork": f"https://www.google.com/search?q={q_both}",
        "Google Fraud / Scam Check Dork": f"https://www.google.com/search?q={q_fraud}",
        "Indonesian Marketplace & Social Dork": f"https://www.google.com/search?q={q_market}",
        "Government / Academic / Document Leak Dork": f"https://www.google.com/search?q={q_docs}",
    }

    return result
