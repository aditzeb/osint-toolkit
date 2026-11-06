"""Conversational control loop: turn free text into pipeline/session actions.

This is what makes SNOOP feel like you're talking to an analyst instead of
running a one-shot scan: "dig deeper on his github", "that's not him, the
chess player is a different guy", "also check if she goes by annab on reddit".
"""

from __future__ import annotations

import json
import re
from shlex import quote as shlex_quote

from snoop import session as sess
from snoop.analyst import _call, _loads
from snoop.config import config
from snoop.core import Bus, detect_kind
from snoop.pipeline import Dossier, investigate


def validated_action(action: dict | None) -> dict | None:
    return action if isinstance(action, dict) else None

SYSTEM = (
    "You are the control loop for SNOOP, an OSINT identity tool. The analyst "
    "talks to you in plain English; you translate that into tool actions. "
    "Be decisive - infer the obvious action rather than asking for clarification "
    "unless the request is genuinely ambiguous."
)

PROMPT = """CURRENT STATE:
{state}

ANALYST SAID: {text!r}

Return ONLY JSON, one action (pick the single best match):
{{"op": "investigate", "target": "...", "kind": "username|name|email|null"}}   - start fresh / look up someone new
{{"op": "command", "command": "search --query \\"...\\" --engine google"}}        - run a registered case command
{{"op": "add_handle", "handle": "..."}}                                        - also check this handle/username
{{"op": "deepen", "platform": "GitHub|Reddit|Lichess|..."}}                     - dig deeper into one account
{{"op": "pick", "label": "A"}}                                                  - confirm identity A/B/C.. as the target
{{"op": "merge", "a": "A", "b": "B"}}                                           - analyst says A and B are the same person
{{"op": "split", "label": "A", "platform": "H03"}}                              - split one exact account reference
{{"op": "context", "fact": "..."}}                                             - analyst states something they KNOW about the subject
{{"op": "ask", "question": "..."}}                                             - a question about the findings, answer from evidence
{{"op": "none", "reply": "..."}}                                               - nothing actionable; just reply conversationally

Registered commands (op=command): plan run step pause continue stop cases resume
case search manual-search accounts aliases read follow document archive domain
image leads queries sources evidence compare verify graph timeline ask report
export providers doctor agent trace connections. "agent" hands the case to the
investigator agent ("keep digging", "figure it out"); "trace H03" shows how a
record was found; "connections" explains links between records. "Search Google for this name" is
{{"op": "command", "command": "search --engine google --query <the name>"}}.

Use op=context whenever the analyst asserts a fact about the subject ("he's from
Toronto", "she works at a bank", "he does chess") - it re-scores every account found
so far against that fact. Statements are context; questions are ask.

If the analyst asks a QUESTION about someone/something already named in CURRENT STATE
(an existing identity, platform, or fact), use op=ask - never op=investigate for a
name you already have data on; investigate is only for a brand-new target.
Always include a short "reply" field (<20 words) except when op is investigate/add_handle/deepen (those report their own result)."""


def _state_summary(dossier: Dossier | None) -> str:
    if not dossier:
        return "(no active investigation)"
    idts = dossier.analysis.get("identities", [])
    lines = [
        f"target: {dossier.target} ({dossier.kind})",
        f"handles tried: {', '.join(dossier.handles_tried)}",
        f"accounts found: {len(dossier.hits)}",
    ]
    for i in idts:
        lines.append(
            f"  {i['label']}: {i.get('name') or 'unnamed'} "
            f"(evidence score {int(i.get('evidence_score', 0))}) "
            f"accounts={i.get('account_ids', [])[:8]}"
            f"{' [SELECTED]' if i.get('selected') else ''}"
        )
    if dossier.deep:
        lines.append(f"already deepened: {', '.join(dossier.deep)}")
    return "\n".join(lines)


def _heuristic_route(dossier: Dossier | None, text: str) -> dict | None:
    """Fast paths that don't need an AI round-trip."""
    t = text.strip()
    low = t.lower()
    m = re.match(r"^anchor\s+(https?://\S+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "anchor", "url": m.group(1)}
    m = re.match(r'^search\s+--context\s+["\'](.+?)["\']$', t, re.IGNORECASE)
    if m and dossier:
        return {"op": "search", "context": m.group(1)}
    m = re.match(r"^evidence\s+(H\d+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "evidence", "ref": m.group(1).upper()}
    m = re.match(r"^compare\s+(H\d+)\s+(H\d+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "compare", "left": m.group(1).upper(), "right": m.group(2).upper()}
    m = re.match(r"^verify\s+(H\d+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "verify", "ref": m.group(1).upper()}
    m = re.match(r"^follow\s+(H\d+)(?:\s+--depth\s+(\d+))?$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "follow", "ref": m.group(1).upper(), "depth": int(m.group(2) or 1)}
    m = re.match(r"^deepen\s+(H\d+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "deepen", "platform": m.group(1).upper()}
    m = re.match(r"^timeline(?:\s+(\w+))?$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "timeline", "label": m.group(1) or ""}
    m = re.match(r"^diff\s+([\w.-]+)\s+([\w.-]+)$", t, re.IGNORECASE)
    if m:
        return {"op": "diff", "before": m.group(1), "after": m.group(2)}
    m = re.match(r"^export(?:\s+--redact)?$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "export", "redact": "--redact" in low}
    if low == "doctor":
        return {"op": "doctor"}
    if low in {"cases", "case list", "list cases"}:
        return {"op": "cases"}
    m = re.match(r"^(keep|discard)\s+(H\d+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": m.group(1).lower(), "ref": m.group(2).upper()}
    if low == "undo" and dossier:
        return {"op": "undo"}
    m = re.match(r"^resume\s+([\w.-]+)$", t, re.IGNORECASE)
    if m:
        return {"op": "resume", "case_id": m.group(1)}
    m = re.match(r"^(pick|it'?s|its|choose)\s+([a-z])\b", low)
    if m:
        return {"op": "pick", "label": m.group(2).upper()}
    m = re.match(r"^merge\s+([a-z])\s+(?:and\s+|with\s+)?([a-z])\b", low)
    if m:
        return {"op": "merge", "a": m.group(1).upper(), "b": m.group(2).upper()}
    m = re.match(r"^split\s+([a-z])\s+(H\d+|[\w. -]+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "split", "label": m.group(1).upper(), "platform": m.group(2).strip()}
    m = re.match(
        r"^(?:dig deeper on|deepen|expand)\s+(?:his |her |their |the )?"
        r"([\w. ]+?)(?:\s+(?:profile|account|page))?$",
        low,
    )
    if m and dossier:
        plat = m.group(1).strip()
        known = {h["platform"].lower(): h["platform"] for h in dossier.hits}
        for k, v in known.items():
            if plat in k or k in plat:
                return {"op": "deepen", "platform": v}
    m = re.match(
        r"^(?:also )?check (?:if .*? goes by |for |)([\w.\-]{2,30})"
        "(?:\\s+on\\s+\\w+)?$",
        low,
    )
    if m and dossier:
        return {"op": "add_handle", "handle": m.group(1)}
    m = re.match(r"^(?:context|know|fyi|note)[: ]+(.+)$", low)
    if m and dossier:
        return {"op": "context", "fact": m.group(1)}

    # --- discovery workflow phrasing -------------------------------------
    m = re.match(
        r"^(?:search|look\s*up|google|brave)[\s]+(?:google\s+|brave\s+|the\s+web\s+|web\s+)?"
        r"(?:for\s+|up\s+)?(.+)$",
        low,
        re.IGNORECASE,
    )
    if m and dossier and re.search(r"\b(for|about|this|that|his|her|their|name)\b", low):
        engine = "google" if "google" in low.split()[:2] or low.startswith("google") else ""
        engine = engine or ("brave" if low.startswith("brave") else "")
        query = m.group(1).strip().strip('"\'')
        if query:
            command = f'search --query "{query}"'
            if engine:
                command += f" --engine {engine}"
            return {"op": "command", "command": command}
    m = re.match(r"^read\s+(https?://\S+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "command", "command": f"read {m.group(1)}"}
    m = re.match(r"^(?:open|inspect)\s+(https?://\S+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "command", "command": f"read {m.group(1)}"}
    if low in {"run", "go", "keep going", "continue", "carry on"} and dossier:
        return {"op": "command", "command": "run"}
    if low in {"step", "one step", "next step"} and dossier:
        return {"op": "command", "command": "step"}
    if low in {"plan", "show plan", "show the plan", "show me the plan", "what's the plan", "whats the plan"} and dossier:
        return {"op": "command", "command": "plan"}
    if low in {"stop", "cancel", "halt", "stop the investigation"} and dossier:
        return {"op": "command", "command": "stop"}
    if low in {"pause", "hold"} and dossier:
        return {"op": "command", "command": "pause"}
    m = re.match(r"^(?:show\s+)?(?:the\s+)?(leads|sources|queries|aliases|graph|accounts|frontier)$", low)
    if m and dossier:
        name = {"frontier": "leads"}.get(m.group(1), m.group(1))
        return {"op": "command", "command": name}
    m = re.match(r"^archive\s+(https?://\S+|[A-Za-z0-9.-]+\.[A-Za-z]{2,})$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "command", "command": f"archive {m.group(1)}"}
    m = re.match(r"^domain\s+([A-Za-z0-9.-]+\.[A-Za-z]{2,})$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "command", "command": f"domain {m.group(1)}"}
    m = re.match(r"^image\s+(https?://\S+)$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "command", "command": f"image {m.group(1)}"}
    m = re.match(
        r"^(?:agent|autopilot|investigate (?:this|it|on your own)|keep digging|dig (?:deeper|in)|"
        r"figure (?:it|this) out|find (?:out )?more(?: about (?:them|him|her|this))?|use your tools|"
        r"work (?:on|through) (?:it|this|the case))\b[\s:,-]*(.*)$",
        low,
    )
    if m and dossier:
        goal = t[len(t) - len(m.group(1)):].strip() if m.group(1) else ""
        return {"op": "command", "command": "agent" + (f" {shlex_quote(goal)}" if goal else "")}
    m = re.match(r"^(?:trace|how did (?:you|we|snoop) find|where did (?:\w+ )?come from)\s+(\S+?)\??$", t, re.IGNORECASE)
    if m and dossier:
        return {"op": "command", "command": f"trace {m.group(1)}"}
    if dossier and re.match(r"^(?:profile|persona|what do (?:we|you) know(?: about (?:him|her|them))?|who is (?:he|she|this|it)|"
                            r"summari[sz]e (?:him|her|them|the person))\??$", low):
        return {"op": "command", "command": "profile"}
    if low in {"connections", "connect the dots", "show connections", "links", "how is it connected"} and dossier:
        return {"op": "command", "command": "connections"}
    if low in {"providers", "provider status"}:
        return {"op": "command", "command": "providers"}
    m = re.match(r"^manual[- ]search\b", low)
    if m and dossier:
        return {"op": "command", "command": t}

    _q_words = (
        "what",
        "who",
        "where",
        "when",
        "why",
        "how",
        "does",
        "do",
        "is",
        "are",
        "can",
        "did",
        "which",
    )
    if dossier and (t.endswith("?") or low.split(" ", 1)[0] in _q_words):
        return {"op": "ask", "question": t}
    if not dossier and detect_kind(t) in ("username", "name", "email"):
        return {"op": "investigate", "target": t, "kind": None}
    return None


async def handle(dossier: Dossier | None, text: str, bus: Bus) -> tuple[Dossier | None, str]:
    if dossier and (config.presenter or bus.redact_values):
        from snoop.privacy import case_identifiers

        bus.redact_values.extend(case_identifiers(dossier))
    from snoop.registry import COMMANDS as _REGISTRY_COMMANDS

    # Replies are natural language, not a second command language. Keep an
    # evidence question ending in '?' available, but otherwise route directly
    # to the persisted interview question before consulting an AI provider.
    if dossier and text.strip() and not text.rstrip().endswith("?"):
        from snoop import interview

        if interview.pending(dossier) and (text.strip().split() or [""])[0].casefold() not in _REGISTRY_COMMANDS:
            from snoop.registry import execute_tokens

            outcome = await execute_tokens(["answer", text], dossier, bus, runtime="talk")
            reply = outcome["text"]
            dossier.history.append({"role": "analyst", "text": text})
            dossier.history.append({"role": "assistant", "text": reply})
            await bus.emit("reply", text=reply, command="answer")
            return dossier, reply

    first_token = (text.strip().split() or [""])[0].casefold()
    if first_token in _REGISTRY_COMMANDS or first_token in {"use", "list-cases", "import-search"}:
        action = {"op": "command", "command": text.strip()}
    else:
        action = _heuristic_route(dossier, text)
    if action is None:
        prompt = PROMPT.format(state=_state_summary(dossier), text=text)
        try:
            raw = await _call(prompt, SYSTEM)
            action = validated_action(_loads(raw)) or {
                "op": "none",
                "reply": "model output was rejected by the action validator",
            }
        except Exception as e:
            action = {"op": "none", "reply": f"(AI unavailable: {e})"}

    action = validated_action(action) or {"op": "none", "reply": "invalid action"}
    op = action.get("op", "none")
    reply = action.get("reply", "")

    if dossier:
        dossier.history.append({"role": "analyst", "text": text})

    if op == "command":
        from snoop import registry as registry_mod

        try:
            result = await registry_mod.execute(action["command"], dossier, bus, runtime="talk")
            dossier = result.get("case") or dossier
            reply = result.get("text", reply)
        except registry_mod.CommandError as exc:
            reply = str(exc)
    elif op == "investigate":
        target = action.get("target") or text
        if config.presenter:
            bus.redact_values.append(target)
        dossier = await investigate(target, bus, kind=action.get("kind"))
        st = dossier.stats
        n = len(dossier.analysis.get("identities", []))
        reply = (
            f"'{target}' - {st.get('linked', 0)} of {st.get('accounts_returned', 0)} "
            f"accounts linked to the subject, {st.get('discarded', 0)} discarded as "
            f"collisions; {n} {'person' if n == 1 else 'people'} identified"
        )
    elif op == "add_handle" and dossier:
        reply = await sess.add_handle(dossier, action.get("handle", ""), bus)
    elif op == "deepen" and dossier:
        reply = await sess.deepen(dossier, action.get("platform", ""), bus)
    elif op == "pick" and dossier:
        reply = await sess.pick(dossier, action.get("label", ""))
    elif op == "merge" and dossier:
        reply = await sess.merge(dossier, action.get("a", ""), action.get("b", ""))
    elif op == "split" and dossier:
        reply = await sess.split_out(dossier, action.get("label", ""), action.get("platform", ""))
    elif op == "context" and dossier:
        reply = await sess.add_context(dossier, action.get("fact", text), bus)
    elif op == "ask" and dossier:
        reply = await sess.ask(dossier, action.get("question", text))
    elif op == "anchor" and dossier:
        from snoop.actions import anchor

        try:
            reply = await anchor(dossier, action.get("url", ""), bus)
        except Exception as exc:
            reply = f"anchor rejected: {exc}"
    elif op == "search" and dossier:
        from snoop.actions import search

        reply = await search(dossier, action.get("context", ""), bus)
    elif op == "evidence" and dossier:
        from snoop.actions import show_evidence

        try:
            reply = json.dumps(show_evidence(dossier, action.get("ref", "")), indent=2)
        except ValueError as exc:
            reply = str(exc)
    elif op == "compare" and dossier:
        from snoop.actions import compare

        try:
            reply = json.dumps(
                compare(dossier, action.get("left", ""), action.get("right", "")), indent=2
            )
        except ValueError as exc:
            reply = str(exc)
    elif op == "verify" and dossier:
        from snoop.actions import verify

        reply = await verify(dossier, action.get("ref", ""), bus)
    elif op == "follow" and dossier:
        from snoop.actions import follow

        reply = await follow(dossier, action.get("ref", ""), bus, action.get("depth", 1))
    elif op == "timeline" and dossier:
        from snoop.actions import timeline

        reply = json.dumps(timeline(dossier, action.get("label", "")), indent=2)
    elif op == "diff":
        from snoop.actions import diff_cases

        before, after = (
            Dossier.load(action.get("before", "")),
            Dossier.load(action.get("after", "")),
        )
        reply = (
            json.dumps(diff_cases(before, after), indent=2)
            if before and after
            else "both saved case IDs must exist"
        )
    elif op == "export" and dossier:
        from snoop.actions import export_case

        reply = json.dumps(
            export_case(
                dossier,
                bool(action.get("redact")) or config.presenter or bool(bus.redact_values),
            ),
            indent=2,
        )
    elif op == "doctor":
        from snoop.actions import doctor

        reply = json.dumps(doctor(), indent=2)
    elif op == "cases":
        reply = json.dumps(Dossier.list_cases(), indent=2)
    elif op == "resume":
        loaded = Dossier.load(action.get("case_id", ""))
        if loaded:
            dossier, reply = (
                loaded,
                f"resumed {loaded.id}: {len(loaded.all_accounts)} account(s), decisions and history restored",
            )
        else:
            reply = f"case {action.get('case_id', '')!r} not found"
    elif op in {"keep", "discard"} and dossier:
        reply = await sess.account_decision(dossier, action.get("ref", ""), op)
    elif op == "undo" and dossier:
        reply = await sess.undo(dossier)
    elif not dossier and op not in ("investigate",):
        reply = "nothing active yet - give me a username, name, or email to start."
    elif not reply:
        reply = "noted."

    if dossier:
        dossier.history.append({"role": "snoop", "text": reply})
        dossier.save()
        await bus.emit("reply", text=reply)
        if op != "investigate":  # investigate() already emitted fresh cards
            cards = sess.build_cards(dossier)
            if cards:
                await bus.emit("cards", identities=cards)
    else:
        await bus.emit("reply", text=reply)
    return dossier, reply
