"""Conservative, explainable identity evidence scoring.

Scores rank leads; they are not probabilities. Dependent observations count once,
and account existence is separate from ownership.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from snoop.model import canonical_url, evidence_record

CONFIRMED, PROBABLE, WEAK, UNRELATED, CONFLICTING, INSUFFICIENT = (
    "confirmed",
    "probable",
    "weak",
    "unrelated",
    "conflicting",
    "insufficient",
)
_NOBILIARY = {"van", "von", "de", "der", "den", "la", "le", "di", "da", "el", "al", "bin", "ibn"}
_DEFAULT_AVATAR = (
    "default",
    "anonymous",
    "placeholder",
    "no-avatar",
    "blank",
    "mystery",
    "identicon",
    "githubassets",
    "opengraph",
    "og-image",
    "logo",
    "favicon",
)


def normalize(value: str) -> str:
    raw = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(re.findall(r"[\w]+", raw, flags=re.UNICODE))


def tokens(value: str) -> list[str]:
    return [t for t in normalize(value).split() if len(t) > 1 and t not in _NOBILIARY]


def normalize_context(context: list[str] | None) -> list[str]:
    return list(dict.fromkeys(n for item in (context or []) if (n := normalize(item))))


def _platform_domains() -> set[str]:
    doms = {
        "twitter.com",
        "x.com",
        "linkedin.com",
        "facebook.com",
        "youtube.com",
        "youtu.be",
        "t.me",
        "linktr.ee",
    }
    try:
        sites = json.loads((Path(__file__).parent / "data" / "sites.json").read_text("utf-8"))[
            "sites"
        ]
        for site in sites:
            host = (urlsplit(site["url"].replace("{}", "x")).hostname or "").lower()
            if host:
                doms.add(host.removeprefix("www."))
    except Exception:
        pass
    return doms


_PLATFORM_DOMAINS = _platform_domains()


def _is_platform_domain(domain: str) -> bool:
    d = domain.lower().removeprefix("www.")
    return any(d == known or d.endswith("." + known) for known in _PLATFORM_DOMAINS)


@dataclass
class Ev:
    points: int
    label: str
    detail: str
    evidence_id: str = ""
    source_url: str = ""
    dependence: str = ""
    supports: bool | None = True
    limitation: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _name_parts(name: str) -> tuple[str, str, list[str]]:
    raw = tokens(name)
    return (raw[0], raw[-1], raw) if raw else ("", "", [])


def handle_conventions(name: str) -> dict[str, tuple[str, int]]:
    first, last, raw = _name_parts(name)
    if not first:
        return {}
    middle = "".join(p[0] for p in raw[1:-1])
    out = {
        first + last: ("full name, joined", 12),
        f"{first}.{last}": ("first.last", 12),
        f"{first}_{last}": ("first_last", 11),
        f"{first}-{last}": ("first-last", 11),
        last + first: ("last+first", 8),
        first[0] + last: ("initial+surname", 7),
        first + last[0]: ("first+initial", 5),
        first: ("given name only", 1),
        last: ("surname only", 2),
    }
    if middle:
        out[first[0] + middle + last] = ("initials+surname", 8)
        out[first + middle + last] = ("first+middle+last", 10)
    return out


def name_match(profile_name: str, subject_name: str) -> Ev | None:
    if not subject_name:
        return None
    p, s = tokens(profile_name), tokens(subject_name)
    if not p:
        return Ev(
            0,
            "profile",
            "no readable profile name",
            dependence="profile-name",
            supports=None,
            limitation="The source did not expose a readable profile name.",
        )
    ps, ss = set(p), set(s)
    if len(s) >= 2 and ps == ss:
        return Ev(
            42,
            "profile",
            f'profile name "{profile_name}" exactly matches the supplied name',
            dependence="profile-name",
        )
    if len(s) >= 2 and ss <= ps:
        return Ev(
            22,
            "profile",
            f'profile name "{profile_name}" contains the supplied full name',
            dependence="profile-name",
        )
    if len(s) >= 2 and s[-1] in ps:
        # Surname-only and near/fuzzy matches ("Bena Lindqvist", "Enis Lindqvist"
        # against "Theo Lindqvist") are observations, never support: they must
        # not turn an unrelated profile into the subject.
        return Ev(
            6,
            "profile",
            f'shares only the surname "{s[-1]}" with the subject',
            dependence="profile-name",
            supports=None,
            limitation="A shared surname or similar spelling is ambiguous and "
            "does not identify the subject.",
        )
    if len(s) >= 2 and s[0] in ps:
        return Ev(
            4,
            "profile",
            f'shares only the given name "{s[0]}" with the subject',
            dependence="profile-name",
            supports=None,
            limitation="A shared given name is ambiguous and does not identify the subject.",
        )
    if len(p) >= 2 and len(s) >= 2 and ps.isdisjoint(ss):
        return Ev(
            -40,
            "contradiction",
            f'profile identifies a different person: "{profile_name}"',
            dependence="profile-name",
            supports=False,
        )
    return Ev(
        -8,
        "profile",
        f'profile name "{profile_name}" does not establish the supplied identity',
        dependence="profile-name",
        supports=None,
    )


def _field_words(value: object) -> set[str]:
    if isinstance(value, dict):
        value = " ".join(str(v) for v in value.values() if isinstance(v, (str, int, float)))
    elif isinstance(value, list):
        value = " ".join(str(v) for v in value)
    return set(tokens(str(value or "")))


def context_match(hit: dict, context: list[str]) -> list[Ev]:
    fields = {
        "bio": hit.get("bio", ""),
        "location": hit.get("location", ""),
        "display_name": hit.get("display_name", ""),
        "links": hit.get("links", []),
        "structured profile fields": hit.get("extra", {}),
    }
    result: list[Ev] = []
    for hint in normalize_context(context):
        wanted = set(tokens(hint))
        matched = next(
            (name for name, value in fields.items() if wanted and wanted <= _field_words(value)),
            None,
        )
        if matched:
            result.append(
                Ev(
                    10,
                    "context",
                    f'user hint "{hint}" matches whole words in {matched}',
                    dependence=f"hint:{hint}",
                    limitation="A user-provided hint is not independent verification.",
                )
            )
    return result[:2]


def _dom(url: str) -> str:
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


def _clean_avatar(url: str) -> str:
    value = (url or "").split("?")[0].strip()
    return (
        ""
        if not value or any(x in value.lower() for x in _DEFAULT_AVATAR)
        else canonical_url(value)
    )


def build_links(hits: list[dict]) -> dict[int, list[Ev]]:
    out = {i: [] for i in range(len(hits))}

    def add(i: int, j: int, points: int, detail: str, dependence: str, limitation: str = ""):
        out[i].append(
            Ev(
                points,
                "cross-link",
                f"{detail} {hits[j].get('ref', hits[j].get('platform'))}",
                source_url=hits[i].get("canonical_url") or hits[i].get("url", ""),
                dependence=dependence,
                limitation=limitation,
            )
        )

    for i, hit in enumerate(hits):
        linked = {canonical_url(x) for x in hit.get("links", []) if isinstance(x, str)}
        for j, other in enumerate(hits):
            if (
                i != j
                and canonical_url(other.get("canonical_url") or other.get("url", "")) in linked
            ):
                key = f"link:{hit.get('account_id', i)}:{other.get('account_id', j)}"
                add(i, j, 28, "explicitly links to", key)
                add(j, i, 18, "is explicitly linked from", key)

    groups: dict[str, list[int]] = {}
    for i, hit in enumerate(hits):
        if av := _clean_avatar(hit.get("avatar", "")):
            groups.setdefault(av, []).append(i)
    for av, group in groups.items():
        if 1 < len(group) <= 4:
            for i in group:
                for j in group:
                    if i != j and hits[i].get("platform") != hits[j].get("platform"):
                        add(
                            i,
                            j,
                            4,
                            "has the same profile photo URL as",
                            f"avatar:{av}",
                            "Images can be copied and are not independent proof.",
                        )

    domains: dict[str, set[int]] = {}
    for i, hit in enumerate(hits):
        for link in hit.get("links", []):
            d = _dom(link)
            if d and not _is_platform_domain(d):
                domains.setdefault(d, set()).add(i)
    for d, group in domains.items():
        if 1 < len(group) <= 4:
            for i in group:
                for j in group:
                    if i != j:
                        add(i, j, 12, f"shares linked domain {d} with", f"domain:{d}")
    return out


@dataclass
class Assessment:
    index: int
    ref: str
    url: str
    score: int
    verdict: str
    evidence: list[Ev] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ref": self.ref,
            "url": self.url,
            "evidence_score": self.score,
            "score": self.score,
            "verdict": self.verdict,
            "evidence": [e.to_dict() for e in self.evidence],
            "limitations": self.limitations,
        }


def _verdict(score: int, evidence: list[Ev]) -> str:
    if any(e.points <= -35 for e in evidence):
        return UNRELATED
    independent = {e.dependence for e in evidence if e.points > 0 and e.label != "handle"}
    has_link = any(e.label == "cross-link" and e.points >= 18 for e in evidence)
    if score >= 55 and len(independent) >= 2 and has_link:
        return CONFIRMED
    if score >= 35 and len(independent) >= 2:
        return PROBABLE
    if score >= 15:
        return WEAK
    if any(e.supports is False for e in evidence):
        return UNRELATED
    # Nothing contradicts the candidate; there is simply not enough information
    # yet. It stays available for follow-up instead of being called a collision.
    return INSUFFICIENT


def assess(
    hits: list[dict], *, target: str, kind: str, context: list[str] | None = None
) -> list[Assessment]:
    links = build_links(hits)
    conventions = handle_conventions(target) if kind == "name" else {}
    result = []
    for i, hit in enumerate(hits):
        ev: list[Ev] = []
        handle = str(
            hit.get("matched_handle") or (hit.get("extra") or {}).get("matched_handle", "")
        ).casefold()
        if kind == "name" and handle in conventions:
            desc, points = conventions[handle]
            ev.append(
                Ev(
                    points,
                    "handle",
                    f"handle matches the {desc} convention",
                    dependence="handle",
                    limitation="A handle pattern alone does not establish ownership.",
                )
            )
        elif kind == "username" and handle and normalize(handle) == normalize(target.lstrip("@")):
            ev.append(
                Ev(
                    2,
                    "handle",
                    "account exists under the searched handle",
                    dependence="handle",
                    limitation="Account existence is separate from target ownership.",
                )
            )
        if kind == "name" and (match := name_match(hit.get("display_name", ""), target)):
            ev.append(match)
        ev.extend(context_match(hit, context or []))
        ev.extend(links[i])
        unique: dict[str, Ev] = {}
        for item in ev:
            key = item.dependence or f"{item.label}:{item.detail}"
            if key not in unique or abs(item.points) > abs(unique[key].points):
                unique[key] = item
        ev = list(unique.values())
        score = max(0, min(100, sum(item.points for item in ev)))
        verdict = _verdict(score, ev)
        limitations = sorted({item.limitation for item in ev if item.limitation})
        if verdict != CONFIRMED:
            limitations.append(
                "Ownership remains unverified; this evidence score is not a probability."
            )
        result.append(
            Assessment(
                i,
                hit.get("ref", hit.get("platform", "")),
                hit.get("url", ""),
                score,
                verdict,
                ev,
                limitations,
            )
        )
    return result


def records_for(hit: dict, assessment: Assessment) -> list[dict]:
    records = []
    for item in assessment.evidence:
        record = evidence_record(
            account_id=hit.get("account_id", ""),
            claim="account-ownership",
            source_url=item.source_url or hit.get("canonical_url") or hit.get("url", ""),
            excerpt=item.detail,
            method=item.label,
            strength=item.points,
            supports=item.supports,
            dependence=item.dependence,
            limitation=item.limitation,
            retrieved_at=hit.get("retrieved_at"),
        )
        item.evidence_id = record["id"]
        records.append(record)
    return records


def summarise(assessments: list[Assessment]) -> dict:
    out = {k: 0 for k in (CONFIRMED, PROBABLE, WEAK, UNRELATED, CONFLICTING, INSUFFICIENT)}
    for item in assessments:
        out[item.verdict] = out.get(item.verdict, 0) + 1
    return out
