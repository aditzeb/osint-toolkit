"""Turn the analyst's free-text answers into clean, labelled profile facts.

"he lives in france" becomes ``Currently living: France`` instead of a
verbatim note. Rules run offline; when an AI provider is configured the model
structures the answer too and its result is cached on the case. Unparsed
answers still appear verbatim as "Known to you".
"""

from __future__ import annotations

import json
import re

from snoop.evidence import normalize

CATEGORIES = {"identity", "work", "skills", "sport", "online", "places"}

_PLACE_ALIASES = {
    "usa": "United States", "us": "United States", "u.s.": "United States", "america": "United States",
    "united states": "United States", "uk": "United Kingdom", "u.k.": "United Kingdom", "england": "England",
    "deutschland": "Germany", "österreich": "Austria", "osterreich": "Austria", "schweiz": "Switzerland",
    "kosova": "Kosovo", "shqiperi": "Albania", "shqipëri": "Albania", "uae": "United Arab Emirates",
    "nyc": "New York", "la": "Los Angeles",
}
_NATIONALITIES = {
    "german", "albanian", "kosovar", "austrian", "swiss", "american", "british", "english", "french", "italian",
    "spanish", "portuguese", "dutch", "belgian", "polish", "czech", "slovak", "hungarian", "romanian",
    "bulgarian", "greek", "turkish", "serbian", "croatian", "bosnian", "slovenian", "macedonian",
    "montenegrin", "ukrainian", "russian", "swedish", "norwegian", "danish", "finnish", "irish", "scottish",
    "canadian", "mexican", "brazilian", "argentinian", "indian", "pakistani", "chinese", "japanese", "korean",
    "australian", "nigerian", "egyptian", "moroccan", "syrian", "iraqi", "iranian", "afghan",
}
_COUNTRIES = {
    "germany", "austria", "switzerland", "albania", "kosovo", "italy", "france", "spain", "portugal",
    "netherlands", "belgium", "poland", "sweden", "norway", "denmark", "finland", "greece", "turkey", "serbia",
    "croatia", "montenegro", "bosnia", "macedonia", "slovenia", "czechia", "hungary", "romania", "bulgaria",
    "ukraine", "ireland", "canada", "australia", "england", "scotland", "uk", "usa", "america", "deutschland",
}
_ACRONYMS = {"mma", "bjj", "it", "ai", "ui", "ux", "ceo", "cto", "cfo", "hr", "pr", "tu", "ufc", "usa", "uk",
             "uae", "nyc", "ml", "qa", "seo", "vr", "ar", "phd", "msc", "bsc"}
_PLATFORMS = {"instagram": "Instagram", "insta": "Instagram", "ig": "Instagram", "tiktok": "TikTok",
              "twitter": "X / Twitter", "x": "X / Twitter", "github": "GitHub", "youtube": "YouTube",
              "twitch": "Twitch", "linkedin": "LinkedIn", "snapchat": "Snapchat", "snap": "Snapchat",
              "facebook": "Facebook", "reddit": "Reddit", "discord": "Discord", "telegram": "Telegram"}
PLATFORM_LABELS = set(_PLATFORMS.values())
_PLATFORM_HANDLE = re.compile(
    r"\b(?P<p>" + "|".join(sorted(_PLATFORMS, key=len, reverse=True)) + r")\b[^@\w]*"
    r"(?:(?:he|she|they)\s+)?(?:(?:goes by|is|as|named|handle is|username is|name is|called|:)\s*)?@?(?P<v>[A-Za-z0-9_.]{2,40})",
    re.IGNORECASE,
)
_FILLER = re.compile(r"^(?:yes|yeah|yep|ya|yup|ok|okay|well|so|um|uh|hmm|right)\b[\s,.!:-]*|"
                     r"\s*\b(?:somewhere(?:\s+around)?|or so|or something|i guess|around there|ish)\s*$",
                     re.IGNORECASE)
_SPORTS = re.compile(
    r"\b(football|soccer|basketball|tennis|boxing|mma|bjj|jiu[- ]?jitsu|wrestling|kickboxing|muay thai|judo|"
    r"karate|running|marathon|cycling|swimming|gym|lifting|weightlifting|powerlifting|climbing|chess|golf|"
    r"volleyball|handball|hockey|skiing|surfing|crossfit|fitness)\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(r"\b(i think|i guess|maybe|probably|possibly|perhaps|not sure|might|i believe|prob)\b",
                    re.IGNORECASE)
_STOP = re.compile(
    r"\s*(?:[,.;!?()]|\s(?:and|but|since|because|for|with|who|where|which|although|though|now|currently|"
    r"i think|maybe|probably|as a|as an|at the moment|right now|at|for)\b).*$",
    re.IGNORECASE | re.DOTALL,
)
_SUBJ = r"(?:he|she|they|him|her|my subject|the subject|this person|[a-z]+)"

# (pattern, category, label, value style); first match per label wins.
_RULES: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(r"\b(?:used to live|lived|previously lived|was living)\s+(?:in|at)\s+(?P<v>[^\d].*)", re.IGNORECASE),
     "places", "Previously lived", "place"),
    (re.compile(r"\b(?:lives|living|live|resides|residing|based|stays|staying|located|settled)\s+"
                r"(?:in|at|near|around|out of)\s+(?P<v>.+)", re.IGNORECASE), "places", "Currently living", "place"),
    (re.compile(r"\b(?:moved|relocated|emigrated)\s+to\s+(?P<v>.+)", re.IGNORECASE), "places", "Currently living", "place"),
    (re.compile(r"\bborn\s+in\s+(?P<v>(?:19|20)\d\d)\b", re.IGNORECASE), "identity", "Born", "raw"),
    (re.compile(r"\bborn\s+(?:in|at)\s+(?P<v>[^\d].*)", re.IGNORECASE), "places", "Born in", "place"),
    (re.compile(r"\b(?:is|are|comes?|originally|was)\s+(?:originally\s+)?from\s+(?P<v>.+)", re.IGNORECASE),
     "places", "From", "place"),
    (re.compile(r"^\s*from\s+(?P<v>.+)", re.IGNORECASE), "places", "From", "place"),
    (re.compile(r"\b(?P<v>\d{1,2})\s*(?:years?\s*old|y/?o|yrs?\b)", re.IGNORECASE), "identity", "Age", "raw"),
    (re.compile(r"\b(?:aged?|age is|is about|around)\s+(?P<v>\d{1,2})\b", re.IGNORECASE), "identity", "Age", "raw"),
    (re.compile(r"\b(?:works?|working|worked)\s+in\s+(?P<v>(?:it|tech|ai|finance|marketing|sales|security|cybersecurity|construction|healthcare|education|logistics|retail|hospitality|software|media|design|engineering|consulting|real estate|gastronomy|automotive)\b.*)", re.IGNORECASE), "work", "Field", "text"),
    (re.compile(r"\b(?:works?|working|worked|employed)\s+(?:as|like)\s+(?:an?\s+)?(?P<v>.+)", re.IGNORECASE),
     "work", "Occupation", "text"),
    (re.compile(r"\b(?:works?|working|employed|interns?|interning)\s+(?:at|for|with)\s+(?P<v>.+)", re.IGNORECASE),
     "work", "Works at", "title"),
    (re.compile(r"\b(?:studies|studying|studied|majoring in|major is)\s+(?P<v>(?!at\b).+?)(?:\s+at\s+.*)?$", re.IGNORECASE),
     "work", "Studies", "text"),
    (re.compile(r"\b(?:studies|studying|studied|goes to|attends|attended|student at|graduated from)\s+"
                r"(?:\S+\s+){0,3}?at\s+(?P<v>.+)", re.IGNORECASE), "work", "Education", "title"),
    (re.compile(r"\b(?:goes to|attends|attended|student at|graduated from)\s+(?P<v>.+)", re.IGNORECASE),
     "work", "Education", "title"),
    (re.compile(r"\bspeaks\s+(?P<v>[a-z]+(?:(?:,\s*|\s+and\s+)[a-z]+){0,4})", re.IGNORECASE),
     "skills", "Languages spoken", "langs"),
    (re.compile(r"\b(?:goes by|known as|nicknamed?|nickname is|calls? (?:him|her|them)self|called)\s+"
                r"(?P<v>\S+(?:\s\S+)?)", re.IGNORECASE), "identity", "Also known as", "raw"),
    (re.compile(r"\b(?:likes|loves|enjoys|is into|into|plays|practices|practises|trains|does|hobby is|"
                r"hobbies are|interested in)\s+(?P<v>.+)", re.IGNORECASE), "skills", "Interest", "text"),
    (re.compile(rf"\b{_SUBJ}(?:\s+is|'s|\s+are|'re)\s+(?:an?\s+)(?P<v>.+)", re.IGNORECASE), "work", "Occupation", "text"),
    (re.compile(r"^\s*(?:an?\s+)(?P<v>.+)", re.IGNORECASE), "work", "Occupation", "text"),
]
_GENERIC = {_RULES[-2][0], _RULES[-1][0]}
_RULES_BY_LABEL = {label: pattern for pattern, _c, label, _s in _RULES}
_URL = re.compile(r"https?://[^\s<>\"')\]]+")
_HANDLE = re.compile(r"(?<![\w.])@([A-Za-z0-9_](?:[A-Za-z0-9_.-]{1,38}[A-Za-z0-9_])?)")


def _defill(value: str) -> str:
    previous = None
    while previous != value:
        previous, value = value, _FILLER.sub("", value).strip()
    return value


def _word(w: str) -> str:
    return w.upper() if w.casefold() in _ACRONYMS else w


def _cut(value: str) -> str:
    value = _defill(_STOP.sub("", value.strip()))
    value = re.sub(r"^(?:the|a|an)\s+", "", value.strip(" '\"-:"), flags=re.IGNORECASE)
    words = value.split()
    return " ".join(words[:5])


def _style(value: str, style: str) -> str:
    value = value.strip(" .") if style == "langs" else _cut(value)
    if not value:
        return ""
    if style == "place":
        key = value.casefold()
        if key in _PLACE_ALIASES:
            return _PLACE_ALIASES[key]
        words = value.split()
        titled = [_word(w) if w.casefold() in _ACRONYMS else w[:1].upper() + w[1:].lower() for w in words]
        # "france lyon area" -> "Lyon area, France"
        if len(words) > 1 and words[0].casefold() in _COUNTRIES:
            country = _PLACE_ALIASES.get(words[0].casefold(), titled[0])
            rest = " ".join(titled[1:]).replace(" Area", " area").replace(" Region", " region")
            return f"{rest}, {country}"
        return " ".join(titled).replace(" Area", " area").replace(" Region", " region")
    if style == "title":
        return " ".join(_word(w) if w.casefold() in _ACRONYMS or any(c.isupper() for c in w[1:])
                        else w[:1].upper() + w[1:] for w in value.split())
    if style == "langs":
        parts = re.split(r",\s*|\s+and\s+", value)
        return ", ".join(p.strip().capitalize() for p in parts if p.strip())
    if style == "text":
        words = [_word(w) for w in value.split()]
        return " ".join([words[0][:1].upper() + words[0][1:], *words[1:]])
    return value


def parse(text: str, question_id: str = "") -> list[dict]:
    """Rule-based structuring of one analyst answer into labelled facts."""
    raw = " ".join(str(text or "").split())
    if not raw:
        return []
    confidence = "likely" if _HEDGE.search(raw) else "stated"
    clean = _HEDGE.sub(" ", raw)
    clean = _defill(re.sub(r"\s+", " ", clean).strip(" ,."))
    facts: list[dict] = []
    seen: set[str] = set()

    def add(category: str, label: str, value: str) -> None:
        if not value or len(value) > 80:
            return
        if label in seen:
            # Several interests/activities combine into one field ("Football, Chess").
            if label in {"Interest", "Activity"}:
                fact = next(f for f in facts if f["label"] == label)
                if value.casefold() not in fact["value"].casefold():
                    fact["value"] = f"{fact['value']}, {value}"
            return
        seen.add(label)
        facts.append({"category": category, "label": label, "value": value, "confidence": confidence})

    for url in _URL.findall(clean)[:3]:
        add("online", "Profile link", url)
    for handle in _HANDLE.findall(clean)[:3]:
        add("online", "Username", "@" + handle)
    for match in _PLATFORM_HANDLE.finditer(clean):
        if match.group("v").casefold() not in {"he", "she", "they", "is", "as", "the", "a", "an", "and", "his", "her"}:
            add("online", _PLATFORMS[match.group("p").casefold()], "@" + match.group("v").lstrip("@"))
    text = _HANDLE.sub(" ", _URL.sub(" ", clean))
    langs = _RULES_BY_LABEL["Languages spoken"].search(text)
    if langs:
        add("skills", "Languages spoken", _style(langs.group("v"), "langs"))
        text = text[:langs.start()] + text[langs.end():]
    # Clauses joined by "and"/"," can each carry a fact ("lives in berlin and works at siemens").
    clauses = [c for c in re.split(r"\s*(?:[,;.]|\band\b|\bbut\b)\s*", text) if c.strip()]
    for clause in clauses:
        for word in re.findall(r"[a-z]+", clause.casefold()):
            if word in _NATIONALITIES and re.search(rf"\b(?:is|are|'s|'re|a|an)\s+{word}\b|^\s*{word}\s*$",
                                                   clause, re.IGNORECASE):
                add("identity", "Nationality", word.capitalize())
        matched = False
        for pattern, category, label, style in _RULES:
            generic = label == "Occupation" and pattern in _GENERIC
            if (label in seen and label not in {"Interest"}) or (generic and matched):
                continue
            match = pattern.search(clause)
            if not match:
                continue
            value = _style(match.group("v"), style)
            if not value or (label == "Occupation" and value.casefold() in _NATIONALITIES):
                continue
            if label == "Age" and not 5 <= int(value) <= 110:
                continue
            if label == "Interest" and _SPORTS.search(value):
                category, label = "sport", "Activity"
            add(category, label, value)
            matched = True
            if generic or label == "Field":
                employer = re.search(r"\s(?:at|for|@)\s+(?P<v>.+)", match.group("v"), re.IGNORECASE)
                if employer:
                    add("work", "Works at", _style(employer.group("v"), "title"))
            if label in {"Interest", "Activity"} or generic:
                # a hobby or a bare job title rarely shares its clause with another field
                break
    # "on instagram he goes by theolind" is one fact (Instagram: @theolind), not also a nickname/username.
    platform_handles = {f["value"].casefold().lstrip("@") for f in facts if f["label"] in PLATFORM_LABELS}
    facts[:] = [f for f in facts if f["label"] not in {"Username", "Also known as"}
                or f["value"].casefold().lstrip("@") not in platform_handles]
    if not facts:
        # A bare answer to a specific question is that field: "france" -> Currently living.
        # "France, Lyon area" is one place answer, so keep both parts for the country question.
        value = _cut(re.sub(r"\s*[,;]\s*", " ", text)) if question_id == "context-country" else _cut(text)
        field = {
            "context-country": ("places", "Currently living", "place"),
            "context-occupation": ("work", "Occupation", "text"),
            "context-handle": ("online", "Username", "raw"),
        }.get(question_id)
        if field and value and len(value.split()) <= 5:
            styled = _style(value, field[2])
            if field[1] == "Username" and not styled.startswith("@"):
                styled = "@" + styled
            add(field[0], field[1], styled)
    return facts


def search_terms(facts: list[dict]) -> str:
    """Compact search refinement from parsed facts ("France", "Renault")."""
    useful = [f["value"] for f in facts if f["category"] in {"places", "work"} or f["label"] == "Also known as"]
    return " ".join(f'"{v}"' if " " in v else v for v in useful[:2])


def _question_for(dossier, context_value: str) -> tuple[str, str]:
    key = normalize(context_value)
    for row in reversed(dossier.interview or []):
        if normalize(str(row.get("value", ""))) == key or normalize(str(row.get("raw", ""))) == key:
            return row.get("id", ""), row.get("raw") or row.get("value", "")
    return "", context_value


def facts_for(dossier, context_value: str) -> tuple[list[dict], str]:
    """Structured facts for one saved context string, plus the analyst's original wording."""
    qid, original = _question_for(dossier, context_value)
    cached = ((dossier.profile or {}).get("answer_facts") or {}).get(normalize(context_value))
    if isinstance(cached, list) and cached:
        return cached, original
    return parse(original, qid), original


_AI_SYSTEM = (
    "You turn an investigator's short answer about a person into clean profile fields. "
    "Use short labels like 'Currently living', 'From', 'Born in', 'Age', 'Occupation', 'Works at', 'Studies', "
    "'Education', 'Languages spoken', 'Interest', 'Activity', 'Nationality', 'Also known as', 'Username'. "
    "Values are short and properly capitalised (a country, a city, a job title) — never the whole sentence. "
    "Mark confidence 'likely' when the investigator hedges. Only include what the answer says. "
    'Return ONLY JSON: {"facts":[{"category":"identity|work|skills|sport|online|places",'
    '"label":"","value":"","confidence":"stated|likely"}]}'
)


async def remember(dossier, answer: str, question: dict | None = None) -> list[dict]:
    """Structure an answer (AI when configured, rules otherwise) and cache it on the case."""
    from snoop.analyst import _call, _loads
    from snoop.config import config

    qid = (question or {}).get("id", "")
    facts = parse(answer, qid)
    if config.ai_provider():
        prompt = (f"Question asked: {(question or {}).get('text', '(free context)')}\n"
                  f"Answer: {json.dumps(str(answer)[:600])}")
        try:
            parsed = _loads(await _call(prompt, _AI_SYSTEM)) or {}
            rows = parsed.get("facts") if isinstance(parsed.get("facts"), list) else []
            ai_facts = [
                {"category": r["category"], "label": str(r["label"]).strip()[:40],
                 "value": " ".join(str(r["value"]).split())[:80],
                 "confidence": "likely" if r.get("confidence") == "likely" else "stated"}
                for r in rows
                if isinstance(r, dict) and r.get("category") in CATEGORIES
                and str(r.get("label", "")).strip() and str(r.get("value", "")).strip()
            ]
            if ai_facts:
                facts = ai_facts[:8]
        except Exception:  # boundary: the rule-based parse stands when the model is unavailable
            pass
    if facts:
        state = dossier.profile or {}
        state.setdefault("answer_facts", {})[normalize(answer)] = facts
        dossier.profile = state
    return facts
