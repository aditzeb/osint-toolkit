"""Offline unit tests - no network."""

from snoop.core import detect_kind, slugify
from snoop.enrich import candidate_emails, candidate_handles, harvest_emails
from snoop.enum import is_username
from snoop.evidence import (
    UNRELATED,
    _is_platform_domain,
    assess,
    build_links,
    handle_conventions,
    name_match,
)
from snoop.session import alias_variants, compare_identities, relabel


def test_detect_kind():
    assert detect_kind("torvalds") == "username"
    assert detect_kind("Ada Lovelace") == "name"
    assert detect_kind("a@b.com") == "email"
    assert detect_kind("example.com") == "domain"
    assert detect_kind("https://x.com/a") == "url"


def test_is_username():
    assert is_username("torvalds")
    assert is_username("john.doe_99")
    assert not is_username("has space")
    assert not is_username("")


def test_candidate_handles_order_and_middle_name():
    h = candidate_handles("Guido van Rossum")
    assert h[0] == "guidorossum"
    assert "gvanrossum" in h  # nobiliary particle kept in one variant
    assert "guido.rossum" in h


def test_candidate_emails():
    e = candidate_emails("jdoe", "John Doe")
    assert any(x.startswith("johndoe@") for x in e)
    assert all("@" in x for x in e)


def test_harvest_emails():
    got = harvest_emails(["reach me at a.b@example.com or nope", "x@y.io"])
    assert "a.b@example.com" in got and "x@y.io" in got


def test_slugify():
    assert slugify("Vuk Sorak!") == "vuk-sorak"


def _hit(platform, ref=None, name="", handle="", avatar="", bio="", loc="", links=None):
    return {
        "platform": platform,
        "ref": ref or platform,
        "url": f"https://{platform.lower()}.com/{handle or 'x'}",
        "display_name": name,
        "bio": bio,
        "location": loc,
        "avatar": avatar,
        "links": links or [],
        "extra": {"matched_handle": handle},
    }


def test_handle_specificity_full_name_beats_given_name():
    conv = handle_conventions("Theo Lindqvist")
    assert conv["theolindqvist"][1] > conv["tlindqvist"][1] > conv["theo"][1]
    assert conv["theo"][1] < 10  # a bare given name proves almost nothing


def test_name_match_rejects_a_different_person():
    assert name_match("Theo Lindqvist", "Theo Lindqvist").points > 40
    surname = name_match("Visar Lindqvist", "Theo Lindqvist")
    assert surname.points < 10 and surname.supports is None  # surname-only is not identity evidence
    neg = name_match("Kacper Nowak", "Theo Lindqvist")
    assert neg.points < 0 and "different person" in neg.detail


def test_collision_is_discarded_but_real_match_is_not():
    hits = [
        _hit("Kaggle", name="Theo Lindqvist", handle="theolindqvist"),
        _hit("Steam", name="Kacper Nowak", handle="theo"),
        _hit("Reddit", handle="theo"),  # nothing readable at all
    ]
    by_ref = {a.ref: a for a in assess(hits, target="Theo Lindqvist", kind="name")}
    assert by_ref["Kaggle"].verdict != UNRELATED
    assert by_ref["Steam"].verdict == UNRELATED
    # A missing display name is insufficient information, not a different
    # person: the candidate stays unresolved and available for follow-up.
    assert by_ref["Reddit"].verdict == "insufficient"


def test_generic_site_card_is_not_treated_as_a_shared_photo():
    card = "https://github.githubassets.com/og-image.png"
    hits = [
        _hit("GitHub Gist", ref="a", avatar=card, handle="x"),
        _hit("GitHub Gist", ref="b", avatar=card, handle="y"),
    ]
    assert build_links(hits)[0] == []  # same platform + generic asset


def test_real_shared_photo_across_platforms_corroborates():
    pic = "https://cdn.example.net/u/1234.jpg"
    hits = [_hit("GitHub", avatar=pic, handle="x"), _hit("Behance", avatar=pic, handle="x")]
    assert any("same profile photo" in e.detail for e in build_links(hits)[0])


def test_platform_subdomain_is_not_a_personal_site():
    assert _is_platform_domain("stories.strava.com")
    assert not _is_platform_domain("chriswanstrath.com")


def test_context_hint_counts_as_evidence():
    h = [_hit("Kaggle", name="Theo Lindqvist", handle="theolindqvist", loc="Warsaw, Poland")]
    plain = assess([dict(h[0])], target="Theo Lindqvist", kind="name")[0].score
    withctx = assess([dict(h[0])], target="Theo Lindqvist", kind="name", context=["poland"])[0].score
    assert withctx > plain


class _D:
    """Minimal stand-in for a Dossier, just enough for session.py's pure helpers."""

    def __init__(self, hits):
        self.hits = hits


def test_relabel_orders_by_confidence_and_dedupes_platforms():
    # "Telegram" is double-claimed (an AI clustering mistake) - the higher-
    # confidence identity keeps it, and an identity left with nothing is dropped.
    analysis = {
        "identities": [
            {"label": "x", "confidence": 0.5, "is_same_person_accounts": ["Telegram"]},
            {"label": "y", "confidence": 0.9, "is_same_person_accounts": ["GitHub", "Telegram"]},
            {"label": "z", "confidence": 0.4, "is_same_person_accounts": ["Reddit"]},
        ]
    }
    relabel(analysis)
    idts = analysis["identities"]
    assert [i["label"] for i in idts] == ["A", "B"]  # "x" got dropped, dead empty
    assert idts[0]["is_same_person_accounts"] == ["GitHub", "Telegram"]
    assert idts[1]["is_same_person_accounts"] == ["Reddit"]


def test_alias_variants_groups_spelling_and_flags_distinct():
    hits = [
        {"platform": "GitHub", "display_name": "Chris Wanstrath", "avatar": "a1"},
        {"platform": "GitLab", "display_name": "chris wanstrath", "avatar": ""},
        {"platform": "Telegram", "display_name": "Mikey", "avatar": ""},
    ]
    idt = {"is_same_person_accounts": ["GitHub", "GitLab"]}
    groups = alias_variants(_D(hits), idt)
    assert len(groups) == 1  # GitHub/GitLab normalise to the same name
    assert set(groups[0]["platforms"]) == {"GitHub", "GitLab"}


def test_compare_identities_flags_shared_avatar_across_clusters():
    hits = [
        {"platform": "GitHub", "avatar": "same.jpg"},
        {"platform": "Telegram", "avatar": "same.jpg"},
    ]
    analysis = {
        "identities": [
            {"label": "A", "name": "chris", "location": "", "is_same_person_accounts": ["GitHub"]},
            {
                "label": "B",
                "name": "mikey",
                "location": "",
                "is_same_person_accounts": ["Telegram"],
            },
        ]
    }
    d = _D(hits)
    d.analysis = analysis
    rows = {r["label"]: r["overlaps"] for r in compare_identities(d)}
    assert rows["A"] and rows["A"][0]["with"] == "B"
    assert "same profile picture" in rows["A"][0]["reasons"]
