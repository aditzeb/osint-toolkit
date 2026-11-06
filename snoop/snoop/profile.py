"""The subject profile: everything the public footprint says or implies.

Facts come from three honest layers, each labelled:

- stated    — the subject's own profile fields/bios or a page about them;
- inferred  — a transparent rule applied to a stated fact
              (e.g. "competes at lightweight in MMA" -> "weighs about 66-70 kg");
- AI        — a model reading cited evidence; every fact must cite existing
              evidence/account IDs and is labelled as AI inference.

Each fact can be confirmed or rejected by the analyst. A rejection of an
account-derived fact discards that account (a recorded constraint); a
confirmation adds the fact as case context and plans a follow-up search.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from snoop.core import Bus
from snoop.model import utcnow

FORBIDDEN = re.compile(r"(?!)")  # never matches
PROFILE_AI_RULES = ""


def blocked_claim(label: str, value: str) -> bool:
    return False


def untrusted(text: str) -> str:
    return text


def validate_ai_fact(raw: dict, known: set, categories: dict, confidence_levels: tuple) -> dict | None:
    if not isinstance(raw, dict):
        return None
    category = raw.get("category", next(iter(categories)))
    if category not in categories:
        category = next(iter(categories))
    return {
        "category": category,
        "label": str(raw.get("label", ""))[:80],
        "value": str(raw.get("value", ""))[:200],
        "cites": list(raw.get("cites") or []),
        "confidence": raw.get("confidence", "possible"),
        "why": str(raw.get("why", ""))[:300],
        "inferred": bool(raw.get("inferred")),
    }


def _eligible_accounts(dossier) -> list[dict]:
    return list(dossier.hits)


CATEGORIES = {
    "identity": "Identity",
    "work": "Work & education",
    "skills": "Skills & interests",
    "sport": "Sport & body",
    "online": "Online presence",
    "places": "Places",
}
CONFIDENCE = ("stated", "likely", "possible")

# Platform presence -> a plausible interest. Presence is a clue, never proof.
PLATFORM_INTERESTS = {
    "GitHub": ("skills", "Writes software", "has a public GitHub account"),
    "GitLab": ("skills", "Writes software", "has a public GitLab account"),
    "GitHub Gist": ("skills", "Writes software", "publishes code snippets on GitHub Gist"),
    "PyPI": ("skills", "Publishes Python packages", "has a PyPI maintainer profile"),
    "npm": ("skills", "Publishes JavaScript packages", "has an npm profile"),
    "Docker Hub": ("skills", "Works with containers", "has a Docker Hub profile"),
    "Kaggle": ("skills", "Interested in data science", "has a Kaggle profile"),
    "HackerOne": ("skills", "Security research / bug bounty", "has a HackerOne profile"),
    "TryHackMe": ("skills", "Learning offensive security", "has a TryHackMe profile"),
    "Stack Overflow": ("skills", "Programming", "has a Stack Overflow profile"),
    "Strava": ("sport", "Runs or cycles", "logs activities on Strava"),
    "AllTrails": ("sport", "Hikes", "has an AllTrails profile"),
    "Lichess": ("skills", "Plays chess", "has a Lichess account"),
    "Chess.com": ("skills", "Plays chess", "has a Chess.com account"),
    "Chess24": ("skills", "Plays chess", "has a Chess24 profile"),
    "Behance": ("skills", "Design / visual work", "publishes on Behance"),
    "Dribbble": ("skills", "Design / visual work", "publishes on Dribbble"),
    "DeviantArt": ("skills", "Makes art", "publishes on DeviantArt"),
    "Flickr": ("skills", "Photography", "publishes on Flickr"),
    "SoundCloud": ("skills", "Makes or shares music", "has a SoundCloud profile"),
    "Bandcamp": ("skills", "Makes music", "has a Bandcamp page"),
    "Mixcloud": ("skills", "DJ / mixes", "has a Mixcloud profile"),
    "YouTube": ("online", "Publishes video", "has a YouTube channel"),
    "Twitch": ("online", "Streams live", "has a Twitch channel"),
    "Medium": ("skills", "Writes articles", "has a Medium profile"),
    "Substack": ("skills", "Writes a newsletter", "has a Substack"),
    "Steam": ("skills", "Plays PC games", "has a Steam profile"),
    "Speedrun.com": ("skills", "Speedruns games", "has a Speedrun.com profile"),
    "Letterboxd": ("skills", "Watches and reviews films", "has a Letterboxd profile"),
    "Goodreads": ("skills", "Reads and reviews books", "has a Goodreads profile"),
    "Duolingo": ("skills", "Learning languages", "has a Duolingo profile"),
    "Smoothcomp": ("sport", "Competes in grappling / combat sports", "is registered on Smoothcomp"),
}

SPORT_CONTEXT = re.compile(
    r"\b(mma|ufc|bellator|bjj|jiu[- ]?jitsu|grappling|no[- ]?gi|submission|smoothcomp|sherdog|tapology|"
    r"boxing|kickboxing|muay thai|k-?1|wrestling|judo|sambo|fight(?:er|s|ing)?|bout|tournament)\b",
    re.IGNORECASE,
)
# MMA (unified rules) upper limits in pounds, ordered light -> heavy.
MMA_CLASSES = [
    ("strawweight", 115), ("flyweight", 125), ("bantamweight", 135), ("featherweight", 145),
    ("lightweight", 155), ("welterweight", 170), ("middleweight", 185),
    ("light heavyweight", 205), ("heavyweight", 265),
]
_LB = 0.45359237


def _kg(lb: float) -> int:
    return round(lb * _LB)


def _fid(category: str, label: str, value: str) -> str:
    key = f"{category}|{label}|{value}".casefold()
    return "fact_" + hashlib.sha256(key.encode()).hexdigest()[:12]


def _snip(text: str, start: int, end: int, width: int = 70) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    out = " ".join(text[left:right].split())
    return ("…" if left else "") + out + ("…" if right < len(text) else "")


class _Builder:
    def __init__(self, dossier):
        self.d = dossier
        self.facts: dict[str, dict] = {}

    def add(self, category: str, label: str, value: str, *, basis: str, confidence: str, why: str,
            source: str = "", source_url: str = "", excerpt: str = "", evidence_ids=None,
            account_id: str = "", derived_from: str = "", origin: str = "rule") -> dict | None:
        value = " ".join(str(value).split())[:120]
        if not value or category not in CATEGORIES or blocked_claim(label, value):
            return None
        fid = _fid(category, label, value)
        fact = self.facts.get(fid)
        if fact:
            # Same fact from another source strengthens it; keep every source.
            if source and source not in fact["sources"]:
                fact["sources"].append(source)
            if basis == "stated" and fact["basis"] != "stated":
                fact.update(basis="stated", confidence="stated", why=why)
            return fact
        fact = {
            "id": fid, "category": category, "label": label, "value": value,
            "basis": basis, "confidence": confidence, "why": why[:300],
            "sources": [source] if source else [], "source_url": source_url,
            "excerpt": excerpt[:240], "evidence_ids": list(evidence_ids or []),
            "account_id": account_id, "derived_from": derived_from, "origin": origin,
        }
        self.facts[fid] = fact
        return fact


def _subject_texts(dossier) -> list[dict]:
    """Text the subject wrote or that is recorded as being about the subject."""
    rows = []
    for h in _eligible_accounts(dossier):
        for field_name in ("bio", "display_name"):
            text = str(h.get(field_name) or "")
            if text:
                rows.append({"text": text, "source": f"{h.get('platform')} {field_name}",
                             "url": h.get("canonical_url", ""), "account_id": h.get("account_id", ""),
                             "evidence_ids": [], "first_party": True})
    for r in dossier.evidence_records:
        if r.get("supports") is False:
            continue
        if not (r.get("supports") or r.get("kind") == "user_statement"):
            continue
        text = f"{r.get('excerpt', '')} {r.get('value', '') if isinstance(r.get('value'), str) else ''}"
        if text.strip():
            domain = str(r.get("source_url", "")).split("//")[-1].split("/")[0]
            rows.append({"text": text, "source": domain or r.get("extraction_method", ""),
                         "url": r.get("source_url", ""), "account_id": r.get("account_id", ""),
                         "evidence_ids": [r["id"]], "first_party": r.get("kind") == "user_statement"})
    return rows


def _rules(b: _Builder, dossier) -> None:
    from snoop.interview import subject_display_name

    name = subject_display_name(dossier)
    b.add("identity", "Name", name, basis="stated", confidence="stated",
          why="the name you entered for this case", source="case input", origin="analyst")
    from snoop.answers import facts_for

    for fact in dossier.context:
        parsed, original = facts_for(dossier, fact)
        for item in parsed:
            b.add(item["category"], item["label"], item["value"], basis="stated",
                  confidence="likely" if item.get("confidence") == "likely" else "stated",
                  why="from what you told SNOOP", source="you", excerpt=original, origin="analyst")
        if not parsed:
            b.add("identity", "Known to you", fact, basis="stated", confidence="stated",
                  why="context you supplied", source="you", origin="analyst")

    accounts = _eligible_accounts(dossier)
    joined = []
    handles: dict[str, list[str]] = {}
    for h in accounts:
        platform = h.get("platform", "")
        strong = h.get("verdict") in {"confirmed", "probable"}
        conf = "likely" if strong else "possible"
        where = f"@{h['matched_handle']}" if h.get("matched_handle") else \
            str(h.get("canonical_url", "")).split("//")[-1].removeprefix("www.").split("/", 1)[-1][:40]
        b.add("online", "Account", f"{platform} {where}".strip(),
              basis="stated", confidence=conf,
              why=f"public {platform} profile; ownership {'supported by evidence' if strong else 'not yet established'}",
              source=platform, source_url=h.get("canonical_url", ""), account_id=h.get("account_id", ""),
              origin="account")
        if h.get("matched_handle"):
            handles.setdefault(h["matched_handle"], []).append(platform)
        if platform in PLATFORM_INTERESTS:
            cat, label, why = PLATFORM_INTERESTS[platform]
            b.add(cat, "Interest" if cat != "sport" else "Activity", label, basis="inferred", confidence="possible",
                  why=f"inferred because the subject {why}", source=platform,
                  source_url=h.get("canonical_url", ""), account_id=h.get("account_id", ""), origin="account")
        if h.get("location"):
            b.add("places", "Profile location", h["location"], basis="stated", confidence=conf,
                  why=f"location field on the {platform} profile (self-reported)", source=platform,
                  source_url=h.get("canonical_url", ""), account_id=h.get("account_id", ""), origin="account")
        if h.get("joined"):
            joined.append((str(h["joined"])[:10], platform))
        deep = (dossier.deep or {}).get(h.get("account_id", "")) or (dossier.deep or {}).get(platform) or {}
        if isinstance(deep, dict):
            langs = deep.get("top_languages") or []
            if langs:
                b.add("skills", "Programming languages", ", ".join(langs[:4]), basis="stated", confidence=conf,
                      why=f"most-used languages across {deep.get('repo_count', 'their')} public repositories",
                      source=platform, source_url=h.get("canonical_url", ""), account_id=h.get("account_id", ""),
                      origin="account")
            ratings = deep.get("ratings") or {}
            if isinstance(ratings, dict) and ratings:
                best = max(ratings.items(), key=lambda kv: kv[1] if isinstance(kv[1], (int, float)) else 0)
                if isinstance(best[1], (int, float)):
                    level = "strong club" if best[1] >= 2000 else "club" if best[1] >= 1600 else "casual"
                    b.add("skills", "Chess level", f"{level} player (~{int(best[1])} {best[0]})", basis="inferred",
                          confidence=conf, why=f"{platform} rating {int(best[1])} in {best[0]}", source=platform,
                          account_id=h.get("account_id", ""), origin="account")
    for handle, platforms in handles.items():
        if len(platforms) >= 2:
            b.add("online", "Main handle", f"@{handle}", basis="inferred", confidence="possible",
                  why=f"the same handle appears on {', '.join(platforms[:4])}", source=", ".join(platforms[:3]),
                  origin="account")
    if joined:
        first = min(joined)
        b.add("online", "Online since", first[0][:4], basis="inferred", confidence="possible",
              why=f"earliest dated account found: {first[1]} joined {first[0]}", source=first[1], origin="account")

    rows = _subject_texts(dossier)
    for row in rows:
        _text_rules(b, row)
    _gender(b, rows)


_DECLARED = re.compile(r"\b(he\s*/\s*him|she\s*/\s*her|they\s*/\s*them)\b", re.IGNORECASE)
_MALE = re.compile(r"\b(he|him|his|himself)\b", re.IGNORECASE)
_FEMALE = re.compile(r"\b(she|her|hers|herself)\b", re.IGNORECASE)


def _gender(b: _Builder, rows: list[dict]) -> None:
    """Male / female / unknown, from stated pronouns first, then from the
    pronouns that pages about the subject use. Never guessed from a name."""
    for row in rows:
        m = _DECLARED.search(row["text"]) if row.get("first_party") else None
        if m:
            said = m.group(1).replace(" ", "").casefold()
            value = {"he/him": "Male", "she/her": "Female"}.get(said, "Unknown")
            b.add("identity", "Gender", value, basis="stated", confidence="stated",
                  why=f"the profile states the pronouns {m.group(1)}", source=row["source"], source_url=row["url"],
                  excerpt=_snip(row["text"], m.start(), m.end()), account_id=row["account_id"], origin="text")
            return
    male = female = 0
    cited: list[str] = []
    for row in rows:
        if row.get("first_party"):
            continue  # a bio's own "his project" rarely refers to the subject
        he, she = len(_MALE.findall(row["text"])), len(_FEMALE.findall(row["text"]))
        male, female = male + he, female + she
        if he or she:
            cited += row["evidence_ids"]
    if male and not female:
        value, why = "Male", f"pages about the subject refer to them as he/him ({male}×)"
    elif female and not male:
        value, why = "Female", f"pages about the subject refer to them as she/her ({female}×)"
    elif male or female:
        value, why = "Unknown", f"mixed pronouns on pages about the subject (he {male}×, she {female}×)"
    else:
        value, why = "Unknown", "no pronouns or stated gender found yet"
    b.add("identity", "Gender", value, basis="inferred", confidence="likely" if max(male, female) >= 2 else "possible",
          why=why, source="pages about them" if cited else "", evidence_ids=cited[:6], origin="text")


def _text_rules(b: _Builder, row: dict) -> None:
    text = row["text"]
    low = text.casefold()
    common = {"source": row["source"], "source_url": row["url"], "evidence_ids": row["evidence_ids"],
              "account_id": row["account_id"], "origin": "text"}

    # Weight classes need a combat-sport context in the same text.
    if SPORT_CONTEXT.search(text):
        for cls_name, limit in sorted(MMA_CLASSES, key=lambda c: -len(c[0])):
            m = re.search(rf"\b{cls_name}\b", low)
            if not m or (cls_name == "heavyweight" and re.search(r"light heavyweight", low)):
                continue
            ordered = [c for c, _ in MMA_CLASSES]
            pos = ordered.index(cls_name)
            lower = MMA_CLASSES[pos - 1][1] if pos else limit - 10
            sport = SPORT_CONTEXT.search(text).group(0)
            fact = b.add("sport", "Competes", f"{cls_name.title()} ({sport})", basis="stated", confidence="stated",
                         why=f"'{cls_name}' appears together with '{sport}'",
                         excerpt=_snip(text, m.start(), m.end()), **common)
            if fact:
                b.add("sport", "Body weight (est.)", f"about {_kg(lower)}–{_kg(limit)} kg", basis="inferred",
                      confidence="likely",
                      why=(f"{cls_name} is the {lower + 1}–{limit} lb class ({_kg(lower)}–{_kg(limit)} kg); "
                           "competitors weigh in near the limit, so fight-week weight is typically within this range"),
                      excerpt=fact["excerpt"], derived_from=fact["id"], **common)
            break
        for m in re.finditer(r"(?:[-−]|under\s*|up to\s*|u)(\d{2,3}(?:[.,]\d)?)\s?kg\b", low):
            kg = float(m.group(1).replace(",", "."))
            if 40 <= kg <= 130:
                fact = b.add("sport", "Competes", f"−{kg:g} kg division", basis="stated", confidence="stated",
                             why="a weight division appears with a combat-sport term",
                             excerpt=_snip(text, m.start(), m.end()), **common)
                if fact:
                    b.add("sport", "Body weight (est.)", f"about {kg - 5:g}–{kg:g} kg", basis="inferred",
                          confidence="likely", why=f"athletes in the −{kg:g} kg division weigh at most {kg:g} kg at weigh-in",
                          excerpt=fact["excerpt"], derived_from=fact["id"], **common)
                break
        m = re.search(r"\b(white|blue|purple|brown|black)\s+belt\b", low)
        if m:
            b.add("sport", "Rank", f"{m.group(1).title()} belt", basis="stated", confidence="stated",
                  why="a belt rank appears with a martial-arts term", excerpt=_snip(text, m.start(), m.end()), **common)
        m = re.search(r"\b(\d{1,3})\s*[-–]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?\s*(?:record|pro|amateur|mma)\b", low)
        if m and int(m.group(1)) < 80 and int(m.group(2)) < 80:
            b.add("sport", "Fight record", "-".join(g for g in m.groups() if g), basis="stated", confidence="stated",
                  why="a win-loss record appears with a combat-sport term", excerpt=_snip(text, m.start(), m.end()), **common)

    m = re.search(r"\b(\d{2})\s?(?:years? old|y/?o)\b", low)
    if m and 13 <= int(m.group(1)) <= 90:
        b.add("identity", "Age", f"{m.group(1)} (at time of writing)", basis="stated", confidence="stated",
              why="an age is written on a page about the subject", excerpt=_snip(text, m.start(), m.end()), **common)
    m = re.search(r"\bborn (?:in |on )?(?:\w+ )?(19[4-9]\d|20[01]\d)\b", low)
    if m:
        year = int(m.group(1))
        now = datetime.now(UTC).year
        fact = b.add("identity", "Born", str(year), basis="stated", confidence="stated",
                     why="a birth year is written on a page about the subject", excerpt=_snip(text, m.start(), m.end()), **common)
        if fact:
            b.add("identity", "Age (est.)", f"{now - year - 1}–{now - year}", basis="inferred", confidence="likely",
                  why=f"born in {year}", derived_from=fact["id"], **common)

    roles = (r"(?:software |security |data |web |mobile |ml |machine learning |devops |cloud |network |"
             r"mechanical |electrical |civil )?(?:engineer|developer|designer|researcher|analyst|consultant|"
             r"founder|co-founder|student|teacher|lecturer|professor|photographer|artist|musician|producer|"
             r"coach|athlete|fighter|writer|journalist|pentester|penetration tester|architect|scientist|manager|"
             r"entrepreneur|freelancer)")
    m = re.search(rf"\b(?:i am|i'm|im|working as|works as|work as|currently)\s+(?:an?\s+)?({roles})\b", low) \
        or (re.search(rf"(?:^|[.!|•\n]\s*)({roles})\b", low) if row.get("first_party") else None)
    if m:
        b.add("work", "Role", m.group(1).title(), basis="stated", confidence="stated" if row.get("first_party") else "likely",
              why="a job title is written by or about the subject", excerpt=_snip(text, m.start(), m.end()), **common)
    m = re.search(rf"\b{roles}\s+(?:at|@)\s+([A-Z][\w&.\-]+(?:\s[A-Z][\w&.\-]+){{0,2}})", text, re.IGNORECASE)
    if m and m.group(1)[0].isupper():
        b.add("work", "Organisation", m.group(1), basis="stated", confidence="likely",
              why="an organisation follows a job title", excerpt=_snip(text, m.start(), m.end()), **common)
    m = re.search(r"\b(?:student at|studies at|studying at|graduate of|graduated from|alumn\w* of)\s+"
                  r"([A-Z][\w&.\-]+(?:\s(?:of\s)?[A-Z][\w&.\-]+){0,4})", text)
    if m:
        b.add("work", "Education", m.group(1), basis="stated", confidence="likely",
              why="a school or university is named as theirs", excerpt=_snip(text, m.start(), m.end()), **common)
    m = re.search(r"\b(?:speaks|fluent in|languages?:)\s+([A-Z][a-z]+(?:(?:,\s*|\s+and\s+)[A-Z][a-z]+){0,4})", text)
    if m:
        b.add("skills", "Languages spoken", m.group(1), basis="stated", confidence="likely",
              why="languages are listed by or about the subject", excerpt=_snip(text, m.start(), m.end()), **common)
    m = re.search(r"\b(?:based in|lives in|living in|from)\s+([A-Z][a-zà-ž]+(?:[ -][A-Z][a-zà-ž]+){0,2})", text)
    if m and m.group(1) not in {"The", "My", "Our"}:
        b.add("places", "Based in", m.group(1), basis="stated", confidence="likely",
              why="a city or country is named as where they are based (region-level only)",
              excerpt=_snip(text, m.start(), m.end()), **common)


def build(dossier) -> dict:
    """Assemble the profile from rules + cached AI facts + analyst reviews."""
    b = _Builder(dossier)
    _rules(b, dossier)
    state = dossier.profile or {}
    known_ids = {r.get("id") for r in dossier.evidence_records} | {h.get("account_id") for h in dossier.all_accounts}
    for raw in state.get("ai_facts", []):
        cites = [c for c in raw.get("cites", []) if c in known_ids]
        if not cites:
            continue
        b.add(raw["category"], raw["label"], raw["value"], basis="inferred" if raw.get("inferred") else "stated",
              confidence=raw.get("confidence", "possible"), why=raw.get("why", ""), source="AI reading",
              evidence_ids=[c for c in cites if c.startswith("ev_")], origin="ai",
              account_id=next((c for c in cites if c.startswith("acct_")), ""))
    reviews = state.get("reviews", {})
    facts = []
    for fact in b.facts.values():
        review = reviews.get(fact["id"], {})
        fact["status"] = review.get("status", "confirmed" if fact["origin"] == "analyst" else "unreviewed")
        fact["note"] = review.get("note", "")
        # A rejected source fact takes its derived inferences with it.
        facts.append(fact)
    rejected_ids = {f["id"] for f in facts if f["status"] == "rejected"}
    for fact in facts:
        if fact["derived_from"] in rejected_ids and fact["status"] == "unreviewed":
            fact["status"] = "rejected"
            fact["note"] = "source fact was rejected"
    order = {c: i for i, c in enumerate(CATEGORIES)}
    rank = {"stated": 0, "likely": 1, "possible": 2}
    facts.sort(key=lambda f: (order[f["category"]], f["status"] == "rejected", rank.get(f["confidence"], 3)))
    live = [f for f in facts if f["status"] != "rejected"]
    return {
        "facts": facts,
        "categories": CATEGORIES,
        "counts": {
            "total": len(live),
            "confirmed": sum(f["status"] == "confirmed" for f in live),
            "inferred": sum(f["basis"] == "inferred" for f in live),
            "rejected": len(facts) - len(live),
        },
        "ai": {"at": state.get("ai_at", ""), "count": len(state.get("ai_facts", [])), "mode": state.get("ai_mode", "")},
    }


async def review(dossier, fact_id: str, status: str, bus: Bus | None = None, note: str = "") -> str:
    """Record the analyst's verdict on one fact and let it steer the case."""
    from snoop import session as sess
    from snoop.leads import LeadQueue

    if status not in {"confirmed", "rejected", "unreviewed"}:
        raise ValueError("status must be confirm, reject or reset")
    profile = build(dossier)
    fact = next((f for f in profile["facts"] if f["id"] == fact_id), None)
    if not fact:
        raise ValueError(f"no fact {fact_id!r} in this profile")
    state = dossier.profile or {}
    reviews = state.setdefault("reviews", {})
    if status == "unreviewed":
        reviews.pop(fact_id, None)
    else:
        reviews[fact_id] = {"status": status, "at": utcnow(), "note": note[:200],
                            "label": fact["label"], "value": fact["value"]}
    dossier.profile = state
    effects = []
    account = dossier.account(fact["account_id"]) if fact.get("account_id") else None
    if status == "rejected" and account and fact["origin"] == "account" and fact["label"] == "Account":
        effects.append(await sess.account_decision(dossier, account["ref"], "discard"))
    elif status == "confirmed" and account and fact["origin"] == "account" and fact["label"] == "Account":
        effects.append(await sess.account_decision(dossier, account["ref"], "keep"))
    elif status == "confirmed" and fact["category"] in {"work", "places", "sport", "skills"} and fact["basis"] == "stated":
        effects.append(await sess.add_context(dossier, fact["value"], bus or Bus()))
        from snoop.interview import subject_display_name

        term = re.sub(r"\s*\(.*?\)", "", fact["value"]).strip()
        if LeadQueue(dossier).add("web_search", {"query": f'"{subject_display_name(dossier)}" {term}'},
                                   f"Follow up the confirmed fact: {fact['label']} = {fact['value']}",
                                   "Pages that match the confirmed fact", origin="user-answer", score=8.0):
            effects.append("planned a follow-up search")
    dossier.record_action("profile_review", fact=fact_id, status=status, label=fact["label"], value=fact["value"])
    dossier.save()
    verb = {"confirmed": "confirmed", "rejected": "marked wrong", "unreviewed": "reset"}[status]
    return f"{fact['label']}: {fact['value']} — {verb}" + (f" ({'; '.join(e for e in effects if e)})" if effects else "")


AI_SYSTEM = (
    "You extract a public profile from public material about ONE person.\n" + PROFILE_AI_RULES + "\n"
    "Allowed categories: identity, work, skills, sport, online, places.\n"
    'Mark inferred=true when you derive it (e.g. a weight class implies a weight range) and explain the rule in "why".\n'
    'Return ONLY JSON: {"facts":[{"category":"","label":"","value":"","inferred":false,'
    '"confidence":"stated|likely|possible","why":"","cites":[""]}]}'
)


async def ai_extract(dossier, bus: Bus | None = None) -> dict:
    """Ask the configured model for additional cited facts; validated and cached."""
    from snoop.analyst import _call, _loads
    from snoop.config import config

    bus = bus or Bus()
    if not config.ai_provider():
        return {"added": 0, "note": "no AI provider configured; rule-based facts only"}
    items = []
    for h in _eligible_accounts(dossier):
        items.append({"id": h.get("account_id"), "type": f"{h.get('platform')} profile",
                      "name": h.get("display_name", ""), "bio": str(h.get("bio", ""))[:400],
                      "location": h.get("location", ""), "joined": h.get("joined", "")})
    for r in dossier.evidence_records:
        if r.get("supports") or r.get("kind") == "user_statement":
            items.append({"id": r.get("id"), "type": r.get("claim"), "text": str(r.get("excerpt", ""))[:500],
                          "source": r.get("source_url")})
    if not items:
        return {"added": 0, "note": "nothing tied to the subject yet"}
    from snoop.interview import subject_display_name

    prompt = (f"Subject: {subject_display_name(dossier)}\n" + untrusted(json.dumps(items[:60], default=str)[:22000])
              + "\nExtract every well-supported fact and reasonable, clearly-labelled inference.")
    await bus.emit("stage", name="AI is reading the evidence for profile facts")
    try:
        parsed = _loads(await _call(prompt, AI_SYSTEM)) or {}
    except Exception as exc:  # boundary: provider failure keeps rule-based facts
        return {"added": 0, "note": f"AI unavailable ({type(exc).__name__})"}
    known = {i["id"] for i in items}
    kept = []
    for raw in parsed.get("facts", []) if isinstance(parsed.get("facts"), list) else []:
        fact = validate_ai_fact(raw, known, CATEGORIES, CONFIDENCE)
        if fact:
            kept.append(fact)
    state = dossier.profile or {}
    state.update(ai_facts=kept[:40], ai_at=utcnow(), ai_mode=config.ai_provider())
    dossier.profile = state
    dossier.save()
    await bus.emit("profile", added=len(kept))
    return {"added": len(kept), "note": f"{len(kept)} cited AI fact(s)"}


def render(profile: dict) -> str:
    lines = []
    for key, title in profile["categories"].items():
        rows = [f for f in profile["facts"] if f["category"] == key and f["status"] != "rejected"]
        if not rows:
            continue
        lines.append(title)
        for f in rows:
            mark = {"confirmed": "✓", "unreviewed": " "}.get(f["status"], " ")
            tag = "inferred" if f["basis"] == "inferred" else f["confidence"]
            lines.append(f"  [{mark}] {f['label']}: {f['value']}  ({tag}; {', '.join(f['sources'][:2]) or 'case'})  {f['id']}")
            if f["basis"] == "inferred":
                lines.append(f"        why: {f['why']}")
    c = profile["counts"]
    lines.append(f"{c['total']} fact(s), {c['confirmed']} confirmed, {c['inferred']} inferred, {c['rejected']} rejected")
    return "\n".join(lines)
