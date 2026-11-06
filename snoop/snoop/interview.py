"""The interview layer: a permanent subject card and one-at-a-time questions.

The subject is the name exactly as the analyst entered it. It stays a separate
card with an honest verification status and is never populated by renaming an
unrelated profile. Questions come from actual uncertainty in the case, are
asked once, accept "I don't know"/Skip/corrections, and every answer updates
the same case: context is re-applied, candidates are re-scored and new search
leads are planned.
"""

from __future__ import annotations

import re

from snoop.answers import PLATFORM_LABELS, remember, search_terms
from snoop.config import config
from snoop.core import Bus
from snoop.model import utcnow

CONFIRMED, CORRECTED, UNSURE, SKIPPED, UNKNOWN = "confirmed", "corrected", "unsure", "skipped", "unknown"

BLOCKED_OUTCOMES = {"blocked", "rate_limited", "unavailable", "login_required", "captcha"}
BLOCK_WORDS = {
    "blocked": "the site blocks automated readers",
    "rate_limited": "the site is rate-limiting",
    "unavailable": "the page did not load",
    "login_required": "it needs a login",
    "captcha": "it shows a CAPTCHA",
}
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
_AT_HANDLE_RE = re.compile(r"(?<![\w.])@([A-Za-z0-9_](?:[A-Za-z0-9_.-]{1,38}[A-Za-z0-9_])?)")

_YES = {
    "yes", "y", "confirm", "confirmed", "correct", "right", "thats right", "that's right",
    "it is", "correct name", "ye", "yep", "yeah", "sure", "confirm name", "exact",
}
_NO = {"no", "n", "wrong", "not right", "incorrect", "nope", "not correct", "false"}
_UNSURE = {
    "unsure", "not sure", "dont know", "don't know", "do not know", "dunno",
    "unknown", "no idea", "maybe", "possibly", "idk", "i dont know", "i don't know",
}
_SKIP = {"skip", "next", "later", "pass", "skip this", "skip question"}
# Sent by the CLI/web when a question gets no reply within SNOOP_QUESTION_TIMEOUT.
TIMEOUT_REPLY = "no reply (timed out)"
# Facts found in sources that are worth a quick yes/no from the analyst.
_CHECKABLE = {"Based in", "Profile location", "Role", "Organisation", "Education", "Languages spoken",
              "Age", "Age (est.)", "Born", "Competes", "Rank"}
_FACT_CHECK_LIMIT = 3

_NAME_HINTS = (
    "it's ",
    "its ",
    "it is ",
    "the name is ",
    "name is ",
    "actually ",
    "correct name is ",
    "should be ",
    "spelled ",
)


def ensure_subject(dossier) -> dict:
    """Create/repair the permanent subject block. Never overwrites answers."""
    subject = getattr(dossier, "subject", None)
    if not isinstance(subject, dict):
        subject = {}
    if not subject.get("input"):
        subject["input"] = dossier.target
    subject.setdefault("name_confirmed", None)
    subject.setdefault("corrected_name", "")
    subject.setdefault("asked_at", "")
    subject.setdefault("answers", [])
    # Legacy cases have no subject field. Always assign the repaired record;
    # merely having a dataclass attribute is not enough when its old value was
    # null or malformed.
    dossier.subject = subject
    return subject


def subject_display_name(dossier) -> str:
    subject = ensure_subject(dossier)
    return subject.get("corrected_name") or subject.get("input") or dossier.target


def subject_status(dossier) -> dict:
    """Honest verification state of the subject card.

    An exact name match alone does not establish identity: 'supported' needs
    an identity that is both user-selected and carries corroborating evidence
    (verdict confirmed/probable), or a confirmed-verdict account.
    """
    subject = ensure_subject(dossier)
    verified_refs: list[str] = []
    for hit in getattr(dossier, "hits", []) or []:
        if hit.get("verdict") in {"confirmed"}:
            verified_refs.append(hit.get("ref", ""))
    identities = (getattr(dossier, "analysis", {}) or {}).get("identities", []) or []
    selected_supported = any(
        i.get("selected") and i.get("status") in {"supported", "user-merged"}
        and any(
            h.get("verdict") in {"confirmed", "probable"}
            for h in dossier.hits
            if h.get("account_id") in i.get("account_ids", [])
        )
        for i in identities
    )
    if verified_refs or selected_supported:
        status = "supported"
        detail = (
            "identity supported by corroborating evidence"
            if selected_supported
            else f"confirmed account(s): {', '.join(r for r in verified_refs if r)}"
        )
    else:
        status = "unverified"
        detail = "identity not yet verified"
    return {
        "name": subject_display_name(dossier),
        "input": subject.get("input", dossier.target),
        "name_confirmed": subject.get("name_confirmed"),
        "corrected_name": subject.get("corrected_name", ""),
        "status": status,
        "detail": detail,
    }


# ------------------------------------------------------------------ questions


def _asked(dossier) -> set[str]:
    return {row.get("id", "") for row in (getattr(dossier, "interview", None) or [])}


def _asked_answer(dossier, question_id: str) -> str | None:
    for row in getattr(dossier, "interview", None) or []:
        if row.get("id") == question_id:
            return str(row.get("kind", ""))
    return None


def _find_result_snippet(dossier, url: str) -> dict | None:
    for query in dossier.queries:
        for result in query.get("results", []):
            if result.get("url") and url.rstrip("/") in str(result.get("url", "")).rstrip("/"):
                return result
    return None


def _topic_from_bio(bio: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z]{4,}", bio or "") if w.casefold() not in {
        "with", "this", "that", "from", "http", "https", "www", "about", "member", "profile",
    }]
    snippet = " ".join((bio or "").split())[:90]
    return snippet or (words[0] if words else "activity")


def next_question(dossier) -> dict | None:
    """The single most useful unasked question, chosen from real uncertainty."""
    from snoop.evidence import tokens

    def exact_name(a: str, b: str) -> bool:
        return True

    ensure_subject(dossier)
    asked = _asked(dossier)
    subject_name = subject_display_name(dossier)
    subject = dossier.subject
    if dossier.kind != "name":
        return None

    # 1. confirm the name once, before anything else trusts it
    if subject.get("name_confirmed") is None and "confirm-name" not in asked:
        return {
            "id": "confirm-name",
            "kind": "confirm-name",
            "text": f'Is "{subject_name}" the correct full name and spelling?',
            "options": ["confirm", "correct", "unsure"],
            "why": "the subject card and quoted full-name searches depend on the exact spelling",
        }

    target_tokens = set(tokens(subject_display_name(dossier)))

    # 2. distinguishing questions for exact-name candidates that carry
    #    distinguishing context (bio/location) — one candidate at a time
    for hit in dossier.hits:
        qid = f"distinguish:{hit.get('account_id', '')}"
        if qid in asked:
            continue
        bio = (hit.get("bio", "") or "").strip()
        location = (hit.get("location", "") or "").strip()
        if exact_name(hit.get("display_name", ""), subject_name) and len(target_tokens) >= 2 and (bio or location):
            topic = _topic_from_bio(bio or location)
            return {
                "id": qid,
                "kind": "distinguish",
                "text": (
                    f'A result with this exact name on {hit.get("platform", "a platform")} '
                    f'mentions "{topic}". Is that relevant to your subject?'
                ),
                "options": ["that's my subject", "not the same person", "i don't know"],
                "why": f"candidate {hit.get('ref', '')} carries distinguishing context",
                "account_ref": hit.get("ref", ""),
            }

    # 3. several people share the exact name: ask what distinguishes them
    exact_hits = [
        h
        for h in dossier.hits
        if exact_name(h.get("display_name", ""), subject_name) and len(target_tokens) >= 2
    ]
    if len(exact_hits) >= 2 and "distinguish-what" not in asked:
        return {
            "id": "distinguish-what",
            "kind": "context",
            "text": (
                f"Multiple results share the exact name {subject_name!r}. "
                "What distinguishes your subject (city, employer, age, field)?"
            ),
            "options": [],
            "why": "two or more exact-name candidates need separation",
        }

    # 4. blocked exact-name leads: can the analyst read what SNOOP cannot?
    blocked = blocked_source_question(dossier)
    if blocked:
        return blocked

    # 5. Context questions are useful only after the current frontier has been
    # explored. Asking them while a newly confirmed exact-name search is still
    # pending interrupts the natural investigate -> clarify -> investigate loop.
    if any(lead.get("status") == "pending" for lead in dossier.leads) and not dossier.workflow.get("at_checkpoint"):
        return None

    check = fact_check_question(dossier, asked)
    if check:
        return check

    # Context questions that measurably refine searches — skipped when an
    # earlier answer already told us (e.g. "he lives in canada" answers country).
    known = _known_labels(dossier)
    covered = {
        "context-country": {"Currently living", "From", "Previously lived", "Born in"},
        "context-occupation": {"Occupation", "Works at", "Field", "Studies", "Education"},
        "context-handle": {"Username", "Profile link", "Also known as", *PLATFORM_LABELS},
    }
    for qid, label, why in (
        ("context-country", "country or city", "location filters discriminate namesakes in search"),
        ("context-occupation", "occupation or main interest", "field-specific queries find bios and talks"),
        ("context-handle", "known username or profile link", "an anchor validates accounts without guessing"),
    ):
        if qid in asked:
            continue
        has_answer = any(
            row.get("id") == qid and row.get("kind") not in {SKIPPED, UNKNOWN, UNSURE}
            for row in (dossier.interview or [])
        )
        if has_answer or known & covered[qid]:
            continue
        hint = {
            "context-country": "e.g. Canada, Paris, …",
            "context-occupation": "e.g. cybersecurity, student, …",
            "context-handle": "e.g. @whoamitang or a profile URL",
        }[qid]
        return {
            "id": qid,
            "kind": "context",
            "text": f"Do you know the subject's {label}?",
            "options": ["i don't know", "skip"],
            "why": why,
            "hint": hint,
        }
    return None


def blocked_source_question(dossier) -> dict | None:
    """Hand a relevant page SNOOP could not open to the analyst, once."""
    asked = _asked(dossier)
    blocked = [
        s
        for s in dossier.sources
        if s.get("outcome") in BLOCKED_OUTCOMES
        and ((s.get("extra") or {}).get("exact_name_result") or (s.get("extra") or {}).get("needs_analyst"))
        and not (s.get("extra") or {}).get("transcribed")
    ]
    for source in blocked[:3]:
        qid = f"known-profile:{source['id']}"
        if qid in asked:
            continue
        host = source.get("url", "").split("//")[-1].split("/")[0]
        return {
            "id": qid,
            "kind": "known-profile",
            "text": (
                f"I can't open {host} myself ({BLOCK_WORDS.get(source.get('outcome', ''), source.get('outcome'))}). "
                "Could you open it in your browser and paste what it shows — name, bio, links — "
                "or paste the profile URL / username?"
            ),
            "options": ["i don't know", "skip"],
            "why": "a page SNOOP cannot read may still be readable by you; what you paste is recorded as manual assistance",
            "source_url": source.get("url", ""),
            "manual_assist": True,
            "hint": "paste page text, a profile URL, or @username",
        }
    return None


def would_unblock(dossier, question: dict | None) -> bool:
    """Only surface 'Needs input' when an answer could actually move the case."""
    if not question:
        return False
    if question["kind"] == "confirm-name":
        return True
    if question["kind"] in {"distinguish", "distinguish-what"}:
        return True
    if question["kind"] in {"known-profile", "agent"}:
        return True
    # generic context questions only matter once discovery has run
    return bool(dossier.queries) or bool(dossier.hits)


def set_pending(dossier, question: dict | None) -> None:
    if hasattr(dossier, "pending_question"):
        if question and not question.get("asked_at"):
            question = {**question, "asked_at": utcnow()}
        dossier.pending_question = question or {}


def pending(dossier) -> dict | None:
    q = getattr(dossier, "pending_question", None)
    return q if isinstance(q, dict) and q.get("id") else None


def _extract_corrected_name(text: str) -> str:
    low = " ".join(text.split()).casefold()
    for hint in _NAME_HINTS:
        if low.startswith(hint) or f" {hint}" in low:
            index = low.find(hint)
            rest = text[index + len(hint) :].strip().strip('"\'.')
            words = re.findall(r"[A-Za-zÀ-ž][A-Za-zÀ-ž'-]*", rest)
            if 2 <= len(words) <= 4:
                return " ".join(w[0].upper() + w[1:] for w in words)
    quoted = re.findall(r'"([^"]{3,60})"', text)
    if quoted and 2 <= len(quoted[0].split()) <= 4:
        return quoted[0].strip()
    return ""


def interpret_reply(question: dict, text: str) -> dict:
    """Map a natural-language reply to a structured answer kind + value."""
    low = " ".join((text or "").split()).casefold().strip()
    if not low:
        return {"kind": SKIPPED, "value": ""}
    if low == TIMEOUT_REPLY:
        return {"kind": SKIPPED, "value": "", "timed_out": True}
    if low in _SKIP or low.startswith("skip"):
        return {"kind": SKIPPED, "value": ""}
    if low in _UNSURE:
        return {"kind": UNKNOWN, "value": ""}
    kind = question.get("kind", "")
    if kind == "confirm-name":
        if question.get("awaiting_correction") and 2 <= len(text.split()) <= 6 and not _extract_corrected_name(text):
            return {"kind": CORRECTED, "value": " ".join(text.split())[:100]}
        if low in _YES or low.startswith("yes"):
            return {"kind": CONFIRMED, "value": ""}
        if low in _NO or low.startswith(("no ", "wrong", "not ")):
            corrected = _extract_corrected_name(text)
            if corrected:
                return {"kind": CORRECTED, "value": corrected}
            return {"kind": UNSURE, "value": "", "needs_name": True}
        corrected = _extract_corrected_name(text)
        if corrected:
            return {"kind": CORRECTED, "value": corrected}
        if any(w in low for w in ("confirm", "right", "correct", "exact")):
            return {"kind": CONFIRMED, "value": ""}
        return {"kind": UNKNOWN, "value": ""}
    if kind == "distinguish":
        if re.search(r"\b(not|different|unrelated|no|isn't|isnt)\b", low) or "other person" in low:
            return {"kind": "not-relevant", "value": ""}
        if any(w in low for w in ("my subject", "that's him", "thats him", "that's her", "thats her", "relevant", "yes it", "is him", "is her", "yes")):
            return {"kind": "relevant", "value": ""}
        return {"kind": UNKNOWN, "value": ""}
    if kind == "fact-check":
        if re.search(r"\b(no|not|wrong|incorrect|isn't|isnt|false|nope)\b", low):
            return {"kind": "rejected", "value": ""}
        if low in _YES or re.search(r"\b(yes|yeah|yep|right|correct|true|that's him|thats him|matches)\b", low):
            return {"kind": CONFIRMED, "value": ""}
        return {"kind": UNKNOWN, "value": ""}
    if kind in {"known-profile", "agent"}:
        # Pasted page text keeps its line structure (bio, links) up to a cap.
        return {"kind": "value", "value": (text or "").strip()[:4000]}
    # context: the reply itself is the value
    return {"kind": "value", "value": " ".join(text.split())[:200]}


def _is_supplied_material(question: dict, value: str) -> bool:
    """A URL, a handle the question asked for, or pasted page text — as
    opposed to a short fact that should become case context."""
    if question.get("source_url") or _URL_RE.search(value) or len(value.split()) > 14 or "\n" in value:
        return True
    return bool(
        re.fullmatch(r"@?[\w.-]{2,40}", value)
        and ("username" in question.get("text", "").casefold() or value.startswith("@"))
    )


def apply_supplied_material(dossier, question: dict, value: str, plan) -> str:
    """Turn what the analyst saw on a page SNOOP could not open into case data.

    A lone URL becomes a validation/read lead, a lone handle a bounded check,
    and anything longer is stored as an analyst-transcribed record labelled
    manual assistance — never as an automated page read — whose URLs and
    @handles become ordinary follow-up leads.
    """
    from snoop.actions import _site_for
    from snoop.discover import find_mentions
    from snoop.model import evidence_record

    value = (value or "").strip()
    words = value.split()
    if len(words) == 1 and value.startswith(("http://", "https://")):
        if _site_for(value):
            plan("check_account", {"url": value}, f"Validate the profile you linked: {value[:70]}",
                 "An analyst-supplied anchor", score=9.0)
        else:
            plan("read_source", {"url": value}, f"Read the page you linked: {value[:70]}",
                 "Mentions and links on the page you supplied", score=8.5)
        return "planned a check of the link you supplied"
    if len(words) == 1 and re.fullmatch(r"@?[\w.-]{2,40}", value):
        handle = value.lstrip("@")
        plan("probe_handles", {"handles": [handle], "origin": "user-answer"},
             f"Check the username you provided: {handle}", "Accounts under the explicitly known handle", score=8.5)
        return f"planned a bounded check of @{handle}"

    source_url = question.get("source_url", "")
    subject = subject_display_name(dossier)
    mentions = find_mentions(value, subject) if subject else []
    record = evidence_record(
        claim="analyst-transcribed-page",
        source_url=source_url or "manual://analyst-transcript",
        source_location="transcribed by the analyst (manual assistance)",
        value=value[:200],
        excerpt=value[:500],
        method="manual-assistance",
        kind="user_statement",
        supports=None,
        limitation=(
            "Transcribed by the analyst from a page SNOOP could not open. Manual assistance, "
            "not an automated read; verify before relying on it."
        ),
    )
    if not any(r.get("id") == record["id"] for r in dossier.evidence_records):
        dossier.evidence_records.append(record)
    for source in dossier.sources:
        if source_url and source.get("url") == source_url:
            extra = source.setdefault("extra", {})
            extra.update(transcribed=True, transcript_evidence=record["id"], mentions_subject=bool(mentions))
    links = list(dict.fromkeys(_URL_RE.findall(value)))[:6]
    handles = [h for h in dict.fromkeys(_AT_HANDLE_RE.findall(value)) if len(h) >= 3][:5]
    for link in links:
        if _site_for(link):
            plan("check_account", {"url": link}, f"Validate a profile link from your transcript: {link[:60]}",
                 "An account the blocked page links", score=8.0)
        else:
            plan("read_source", {"url": link}, f"Read a link from your transcript: {link[:60]}",
                 "Pages the blocked page points to", score=7.5)
    for handle in handles:
        plan("web_search", {"query": f'"{handle}"'}, f'Search handle "@{handle}" from your transcript',
             "Pages and accounts using this handle", score=7.5)
    parts = [f"recorded your transcript as {record['id']} (manual assistance)"]
    if mentions:
        parts.append("it mentions the subject by name")
    if links or handles:
        parts.append(f"{len(links)} link(s) and {len(handles)} handle(s) queued for follow-up")
    return "; ".join(parts)


async def apply_answer(dossier, text: str, bus: Bus | None = None) -> dict:
    """Apply one answer to the pending question. Returns a summary and the
    follow-up leads that were planned."""
    from snoop import session as sess
    from snoop.leads import LeadQueue
    from snoop.pipeline import apply_assessments

    bus = bus or Bus()
    question = pending(dossier)
    if not question:
        return {"text": "no pending question; 'questions' shows what the investigation needs", "leads": 0}
    reply = interpret_reply(question, text)
    if question.get("kind") == "confirm-name" and (
        reply.get("needs_name") or text.strip().casefold() == "correct"
    ):
        question = dict(question, text="What is the corrected full name? Enter the full name, or Skip.", awaiting_correction=True)
        set_pending(dossier, question)
        dossier.save()
        await bus.emit("question", question=question)
        return {"text": question["text"], "leads": 0, "reply": reply}
    ensure_subject(dossier)
    subject = dossier.subject
    qid = question["id"]
    dossier.interview = [
        *(row for row in (dossier.interview or []) if row.get("id") != qid),
        {
            "id": qid,
            "question": question.get("text", ""),
            "kind": reply["kind"],
            "raw": " ".join((text or "").split())[:300],
            "value": reply.get("value", ""),
            "at": utcnow(),
        },
    ]
    queue = LeadQueue(dossier)
    planned = 0
    notes: list[str] = []

    def plan(lead_type: str, args: dict, purpose: str, expected: str = "", score: float = 6.0) -> None:
        nonlocal planned
        if queue.add(lead_type, args, purpose, expected, origin="user-answer", score=score):
            planned += 1

    name = subject_display_name(dossier)
    if question["kind"] == "confirm-name":
        if reply["kind"] == CONFIRMED:
            subject["name_confirmed"] = True
            subject["asked_at"] = utcnow()
            plan(
                "web_search",
                {"query": f'"{name}"'},
                f'Prioritized exact-name search for the confirmed subject "{name}"',
                "The highest-value pages for the exact confirmed name",
                score=9.5,
            )
            notes.append("name confirmed — quoted full-name search prioritized")
        elif reply["kind"] == CORRECTED and reply.get("value"):
            subject["name_confirmed"] = True
            subject["corrected_name"] = reply["value"]
            # Preserve old evidence, but don't continue searches/probes planned
            # against the misspelling. Newly planned work uses the correction.
            for lead in dossier.leads:
                if lead.get("origin") == "planner" and lead.get("status") in {"pending", "deferred"}:
                    lead.update(status="rejected", reason="superseded by corrected subject name")
            for query in (f'"{reply["value"]}"', reply["value"]):
                plan(
                    "web_search",
                    {"query": query},
                    f'Search with the corrected subject name "{reply["value"]}"',
                    "Results for the corrected spelling",
                    score=9.5,
                )
            notes.append(f'subject name corrected to "{reply["value"]}"')
        else:
            subject["name_confirmed"] = None
            notes.append("name left unconfirmed — searches keep the entered spelling")
    elif question["kind"] == "distinguish":
        ref = question.get("account_ref", "")
        if reply["kind"] == "relevant":
            message = await sess.account_decision(dossier, ref, "keep")
            notes.append(f"marked {ref} relevant by your answer ({message})")
        elif reply["kind"] == "not-relevant":
            message = await sess.account_decision(dossier, ref, "discard")
            notes.append(f"set {ref} aside by your answer ({message})")
        else:
            notes.append("noted — candidate stays unresolved")
    elif question["kind"] == "known-profile":
        value = reply.get("value", "")
        if reply["kind"] == "value" and value:
            notes.append(apply_supplied_material(dossier, question, value, plan))
        else:
            notes.append("noted — the blocked result stays an unverified lead")
    elif question["kind"] == "agent":
        value = reply.get("value", "")
        if reply["kind"] != "value" or not value:
            notes.append("noted — the agent will continue without it")
        elif _is_supplied_material(question, value):
            notes.append(apply_supplied_material(dossier, question, value, plan))
        else:
            facts = await remember(dossier, value, question)
            _plan_handles(facts, plan)
            message = await sess.add_context(dossier, value, bus)
            terms = search_terms(facts) or value
            plan(
                "web_search",
                {"query": f'"{name}" {terms}'},
                f'Search "{name}" with your answer "{value[:60]}"',
                "Results that satisfy the fact you supplied",
                score=8.0,
            )
            notes.append(_describe(facts) or f"answer applied as context: {message}")
    elif question["kind"] == "context":
        value = reply.get("value", "")
        if reply["kind"] == "value" and value:
            facts = await remember(dossier, value, question)
            _plan_handles(facts, plan)
            message = await sess.add_context(dossier, value, bus)
            terms = search_terms(facts) or value
            plan(
                "web_search",
                {"query": f'"{name}" {terms}'},
                f'Search "{name}" with the new fact "{terms}"',
                "Results that satisfy the distinguishing fact",
                score=8.0,
            )
            notes.append(_describe(facts) or f"context applied and re-scored: {message}")
            if qid == "context-handle":
                if value.startswith(("https://", "http://")):
                    plan("read_source", {"url": value}, "Read the public anchor supplied in the interview", score=9.5)
                elif re.fullmatch(r"@?[\w.-]{2,40}", value):
                    plan("probe_handles", {"handles": [value.lstrip("@")], "origin": "user-answer"},
                         "Check the known username supplied in the interview", score=9.0)
            elif qid in {"context-country", "context-occupation", "distinguish-what"}:
                for suffix in ('profile OR biography', 'project OR publication', 'interview OR speaker'):
                    plan("web_search", {"query": f'"{name}" {terms} {suffix}'},
                         f"Test the new context against {suffix}", score=7.0)
        else:
            notes.append("no context added")
    elif question["kind"] == "fact-check":
        from snoop.profile import review

        fact_id = question.get("fact_id", "")
        if reply["kind"] == CONFIRMED:
            notes.append(await review(dossier, fact_id, "confirmed", bus))
        elif reply["kind"] == "rejected":
            notes.append(await review(dossier, fact_id, "rejected", bus))
        else:
            notes.append("noted — that fact stays unreviewed")
    if reply.get("timed_out"):
        notes = [f"no reply within {config.question_timeout}s — skipped; the investigation continues"]

    # Answers change the interpretation of existing candidates as well as the
    # next search. Rebuild deterministic hypotheses from the same saved case;
    # account selections remain constraints, never new evidence.
    apply_assessments(dossier, dossier.all_accounts)
    dossier.analysis = sess.reconcile_analysis(dossier, sess.deterministic_grouping(dossier))

    set_pending(dossier, None)
    dossier.workflow.pop("at_checkpoint", None)
    dossier.workflow.update({"status": "ready", "answered_at": utcnow(), "stop_reason": ""})
    dossier.record_action("answer", question=qid, kind=reply["kind"], value=reply.get("value", ""), leads=planned)
    dossier.save()
    await bus.emit("answer", question=qid, answer_kind=reply["kind"], planned_leads=planned)
    follow = None if any(l.get("status") == "pending" for l in dossier.leads) else next_question(dossier)
    set_pending(dossier, follow)
    if follow:
        dossier.workflow.update({"status": "needs_input", "stop_reason": f"needs input: {follow['text']}"})
    dossier.save()
    if follow:
        await bus.emit("question", question=follow)
    summary = "; ".join(n for n in notes if n) or "answer recorded"
    if planned:
        summary += f" — {planned} follow-up action(s) planned"
    return {"text": summary, "leads": planned, "reply": reply, "timed_out": bool(reply.get("timed_out"))}


def _plan_handles(facts: list[dict], plan) -> None:
    """A handle the analyst names ("on instagram he goes by x") becomes a bounded account check."""
    for fact in facts:
        if fact["category"] == "online" and str(fact["value"]).startswith("@"):
            handle = fact["value"].lstrip("@")
            plan("probe_handles", {"handles": [handle], "origin": "user-answer"},
                 f"Check the {fact['label']} handle you gave: @{handle}", "Accounts under the handle you named",
                 score=9.0)


def _describe(facts: list[dict]) -> str:
    if not facts:
        return ""
    shown = "; ".join(f"{f['label']}: {f['value']}" for f in facts[:4])
    return f"context applied — added to the profile: {shown}"


def _known_labels(dossier) -> set[str]:
    """Profile labels the analyst has already given, so we never ask for them again."""
    from snoop.answers import facts_for

    labels: set[str] = set()
    for value in dossier.context or []:
        labels.update(f["label"] for f in facts_for(dossier, value)[0])
    return labels


def fact_check_question(dossier, asked: set[str]) -> dict | None:
    """Ask the analyst to confirm one specific fact a public source stated."""
    from snoop.profile import build

    if sum(q.startswith("fact-check:") for q in asked) >= _FACT_CHECK_LIMIT:
        return None
    try:
        facts = build(dossier)["facts"]
    except Exception:  # boundary: a profile rule bug must not stop questions
        return None
    ranked = sorted(
        (f for f in facts
         if f.get("label") in _CHECKABLE and f.get("status") == "unreviewed" and f.get("origin") != "analyst"
         and f"fact-check:{f['id']}" not in asked),
        key=lambda f: {"stated": 0, "likely": 1}.get(f.get("confidence"), 2),
    )
    if not ranked:
        return None
    fact = ranked[0]
    source = ", ".join(fact.get("sources", [])[:2]) or "a public source"
    return {
        "id": f"fact-check:{fact['id']}",
        "kind": "fact-check",
        "text": f'{source} says {fact["label"].lower()}: "{fact["value"]}". Does that match your subject?',
        "options": ["yes, that's right", "no, that's wrong", "i don't know"],
        "why": "confirming or rejecting a found fact steers which pages and accounts count",
        "fact_id": fact["id"],
    }
