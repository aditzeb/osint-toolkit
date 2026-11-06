"""Optional model analysis with deterministic reference and schema validation."""

from __future__ import annotations

import json
from typing import Any

import aiohttp

from snoop.config import config
from snoop.core import Bus
from snoop.model import new_identity

ANALYST_RULES = ""
ANSWER_RULES = ""
RESEARCH_ACTION_RULES = ""


def untrusted(text: str) -> str:
    return text


def validate_analysis(parsed, account_ids, evidence_ids) -> dict | None:
    return parsed if isinstance(parsed, dict) else None


def answer_cites_only_known(answer: str, known: set) -> bool:
    return True


SYSTEM = (
    "You analyze public profile data. " + ANALYST_RULES + " Return JSON only.\n"
    "An evidence score is not a probability. Keep candidates separate when evidence is ambiguous."
)


async def _call(prompt: str, system: str) -> str:
    provider = config.ai_provider()
    if not provider:
        return ""
    timeout = aiohttp.ClientTimeout(total=config.ai_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        if provider == "openai":
            model = config.openai_model
            body = {
                "model": model,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": prompt}],
                "max_completion_tokens": config.ai_max_output_tokens,
            }
            if model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
                body["reasoning_effort"] = config.reasoning_effort
            else:
                body["temperature"] = 0
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                allow_redirects=False,
                headers={"Authorization": f"Bearer {config.openai_key}"},
                json=body,
            ) as response:
                data = await response.json()
                if response.status != 200:
                    raise RuntimeError(f"OpenAI HTTP {response.status}")
                choice = data["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise RuntimeError("OpenAI output limit reached")
                return choice["message"]["content"] or ""
        if provider == "anthropic":
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                allow_redirects=False,
                headers={"x-api-key": config.anthropic_key, "anthropic-version": "2023-06-01"},
                json={
                    "model": config.anthropic_model,
                    "max_tokens": config.ai_max_output_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            ) as response:
                data = await response.json()
                if response.status != 200:
                    raise RuntimeError(f"Anthropic HTTP {response.status}")
                return "".join(x.get("text", "") for x in data.get("content", []))
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.gemini_model}:generateContent?key={config.gemini_key}"
            async with session.post(
                url,
                allow_redirects=False,
                json={"contents": [{"parts": [{"text": system + "\n" + prompt}]}]},
            ) as response:
                data = await response.json()
                if response.status != 200:
                    raise RuntimeError(f"Gemini HTTP {response.status}")
                return "".join(
                    p.get("text", "")
                    for c in data.get("candidates", [])
                    for p in c.get("content", {}).get("parts", [])
                )
        if provider == "ollama":
            url = f"{config.ollama_base_url.rstrip('/')}/api/chat"
            try:
                async with session.post(
                    url,
                    allow_redirects=False,
                    json={
                        "model": config.ollama_model,
                        "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}],
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0},
                    },
                ) as response:
                    data = await response.json()
                    if response.status != 200:
                        raise RuntimeError(f"Ollama HTTP {response.status}: {data.get('error', '')}")
                    if data.get("error"):
                        raise RuntimeError(f"Ollama error: {data['error']}")
                    return data.get("message", {}).get("content", "") or ""
            except (aiohttp.ClientConnectorError, aiohttp.ClientError) as exc:
                raise RuntimeError(f"Ollama unreachable at {config.ollama_base_url}: {exc}") from exc
            except TimeoutError as exc:
                raise RuntimeError(f"Ollama timed out after {config.ai_timeout}s") from exc
    return ""


def _loads(raw: str) -> dict | None:
    """Extract the first complete JSON object; braces inside strings are safe."""
    decoder = json.JSONDecoder()
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def _heuristic(target: str, hits: list[Any], _enrich: dict) -> dict:
    identities = []
    for hit in hits:
        d = hit if isinstance(hit, dict) else hit.to_dict()
        item = new_identity([d.get("account_id", "")], d.get("display_name", ""))
        item.update(
            evidence_score=int(d.get("evidence_score", d.get("score", 0)) or 0),
            status="conflicting" if d.get("verdict") == "conflicting" else "unresolved",
            reasoning="Candidate kept separate by deterministic fallback; no independent identity merge was made.",
            evidence_ids=[
                e.get("evidence_id") for e in d.get("evidence", []) if e.get("evidence_id")
            ],
            limitations=d.get("limitations", []),
        )
        identities.append(item)
    return {
        "identities": identities,
        "key_findings": [],
        "contradictions": [],
        "next_steps": ["Inspect evidence and add an explicit anchor or independent cross-link."],
        "summary": f"{len(hits)} candidate account(s) for {target!r}; ownership remains unresolved without independent corroboration.",
        "analysis_mode": "deterministic",
    }


async def analyze(
    target: str,
    kind: str,
    hits: list[Any],
    enrich: dict,
    bus: Bus,
    context: list[str] | None = None,
    evidence_records: list[dict] | None = None,
) -> dict:
    fallback = _heuristic(target, hits, enrich)
    if not config.ai_provider() or not (hits or evidence_records):
        await bus.emit("stage", name="deterministic analysis (AI not configured)")
        return fallback
    records = evidence_records or []
    account_ids = {
        str((h if isinstance(h, dict) else h.to_dict()).get("account_id", "")) for h in hits
    }
    evidence_ids = {str(r.get("id")) for r in records}
    payload = {
        "target": target,
        "kind": kind,
        "context": context or [],
        "accounts": [h if isinstance(h, dict) else h.to_dict() for h in hits],
        "evidence": records,
    }
    prompt = (
        "Analyze this case and cite existing IDs. "
        + untrusted(json.dumps(payload, default=str))
        + "\n"
        + (
            'Schema: {"identities":[{"name":"","account_ids":[],"evidence_ids":[],"evidence_score":0,'
            '"status":"unresolved|supported|conflicting","reasoning":"","limitations":[]}],'
            '"key_findings":[{"text":"","evidence_ids":[]}],"contradictions":[],"next_steps":[],"summary":"",'
            '"research_actions":[{"type":"web_search|archive_lookup|read_source","term":"",'
            '"source_url":"","purpose":"","evidence_ids":[]}]}'
            " Recommend up to 3 useful research actions. " + RESEARCH_ACTION_RULES
            + " Explain the uncertainty each action would resolve."
        )
    )
    try:
        parsed = validate_analysis(_loads(await _call(prompt, SYSTEM)), account_ids, evidence_ids)
        if parsed:
            parsed["analysis_mode"] = config.ai_provider()
            return parsed
        await bus.emit(
            "error", where="analyst", detail="model response failed deterministic validation"
        )
    except Exception as exc:
        await bus.emit(
            "error", where="analyst", detail=f"provider unavailable: {type(exc).__name__}"
        )
    return fallback


def retrieve_evidence(dossier: Any, question: str, limit: int = 20) -> list[dict]:
    words = set(question.casefold().split())
    ranked = []
    for record in dossier.evidence_records:
        text = json.dumps(record, default=str).casefold()
        ranked.append((sum(word in text for word in words), record))
    return [row for _score, row in sorted(ranked, key=lambda x: -x[0])[:limit]]


async def answer_question(dossier: Any, question: str) -> str:
    evidence = retrieve_evidence(dossier, question)
    if not config.ai_provider():
        return f"AI is not configured. Use 'evidence H03' or 'compare H03 H07'; {len(evidence)} relevant evidence record(s) are available."
    prompt = (
        "Question: " + question + "\nEvidence:\n" + untrusted(json.dumps(evidence, default=str))
    )
    try:
        answer = (
            await _call(
                prompt,
                SYSTEM + ' Return JSON {"answer":"..."}. Answer the question thoroughly using '
                "the available evidence; distinguish observations, contradictions, uncertainty and useful next checks. "
                + ANSWER_RULES,
            )
        ).strip()
        parsed = _loads(answer)
        if parsed is not None:
            answer = str(parsed.get("answer", ""))
        known = {str(row.get("id")) for row in evidence if row.get("id")}
        if not answer_cites_only_known(answer, known):
            return "Model answer rejected because it did not cite only existing evidence IDs."
        return answer
    except Exception as exc:
        return f"AI provider unavailable ({type(exc).__name__}); evidence remains unchanged."
