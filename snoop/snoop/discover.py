"""Working discovery methods: pages, crawls, documents, archives, domains, images.

Every method returns structured sources, evidence clues and follow-up leads,
and feeds its discoveries back into the planner. Structured data (JSON-LD
Person/sameAs, rel=me, author metadata) is treated as a *source assertion*,
never as independent proof, and untrusted page text is never executed or
interpreted as instructions.
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import re
import socket
import zlib
from pathlib import PurePosixPath
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup

from snoop.config import config
from snoop.core import Bus, Http
from snoop.model import canonical_url, source_record, utcnow

_TEXT_CAP = 20000
_PDF_PAGE_CAP = 40
_DOC_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_PLATFORM_JUNK = ("googleapis.com", "gstatic.com", "googletagmanager.com", "w3.org", "schema.org")


# ----------------------------------------------------------------- page reading


def _strip_junk(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(
        ["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]
    ):
        # Structured data is content, not chrome: keep application/ld+json.
        if tag.name == "script" and (tag.get("type") or "").strip().casefold() in {
            "application/ld+json",
            "application/json",
        }:
            continue
        tag.decompose()


def _main_text(soup: BeautifulSoup) -> str:
    root = soup.find("main") or soup.find("article") or soup.body or soup
    text = root.get_text(" ")
    return re.sub(r"\s+", " ", text).strip()[:_TEXT_CAP]


def _jsonld_persons(soup: BeautifulSoup) -> list[dict]:
    persons = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (ValueError, TypeError):
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict):
                continue
            types = node.get("@type", "")
            types = types if isinstance(types, list) else [types]
            if not any(t in {"Person", "ProfilePage"} for t in types):
                continue
            if isinstance(node.get("@graph"), list):
                inner = [g for g in node["@graph"] if isinstance(g, dict) and g.get("@type") == "Person"]
                persons.extend(inner)
                continue
            persons.append(node)
    out = []
    for node in persons[:10]:
        same_as = node.get("sameAs", [])
        if isinstance(same_as, str):
            same_as = [same_as]
        alternates = node.get("alternateName", [])
        if isinstance(alternates, str):
            alternates = [alternates]
        out.append(
            {
                "name": str(node.get("name", "")),
                "alternate_names": [str(a) for a in alternates][:8],
                "same_as": [str(s) for s in same_as if isinstance(s, str)][:20],
                "url": str(node.get("url", "") or ""),
                "description": str(node.get("description", ""))[:300],
            }
        )
    return out


def classify_links(soup: BeautifulSoup, base_url: str) -> dict[str, list[str]]:
    """Split outbound links into feeds, documents, images and plain links."""
    feeds: list[str] = []
    for tag in soup.find_all("link", rel=lambda v: v and "alternate" in v):
        kind = (tag.get("type") or "").lower()
        if kind in {"application/rss+xml", "application/atom+xml", "application/feed+json"} and tag.get(
            "href"
        ):
            feeds.append(urljoin(base_url, tag["href"]))
    rel_me: list[str] = []
    documents: list[str] = []
    images: list[str] = []
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = urljoin(base_url, tag["href"].strip())
        if not href.startswith(("http://", "https://")):
            continue
        rels = " ".join(tag.get("rel") or [])
        path = urlsplit(href).path.casefold()
        suffix = PurePosixPath(path).suffix
        if "me" in rels.split():
            rel_me.append(href)
        elif suffix in _DOC_SUFFIXES:
            documents.append(href)
        elif suffix in _IMAGE_SUFFIXES:
            images.append(href)
        links.append(href)
    seen: set[str] = set()

    def uniq(rows: list[str]) -> list[str]:
        out = []
        for row in rows:
            key = canonical_url(row)
            if key not in seen and row not in seen:
                seen.add(key)
                seen.add(row)
                out.append(row)
        return out

    return {
        "feeds": uniq(feeds)[:6],
        "rel_me": uniq(rel_me)[:20],
        "documents": uniq(documents)[:20],
        "images": uniq(images)[:20],
        "links": uniq(links)[:120],
    }


def find_mentions(text: str, subject: str, *, author: str = "") -> list[dict]:
    """Locate the subject on a page and classify the role honestly."""
    wanted = subject.split()
    if not wanted or not text:
        return []
    pattern = r"(?<!\w)" + r"[\W_]+".join(re.escape(w) for w in wanted) + r"(?!\w)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return []
    index = match.start()
    role = "author" if author and re.search(pattern, author, re.IGNORECASE) else "mentioned"
    start = max(0, index - 120)
    excerpt = re.sub(r"\s+", " ", text[start : match.end() + 120]).strip()
    return [{"name": subject, "role": role, "excerpt": excerpt[:320]}]


def _handle_candidates(text: str, links: list[str]) -> list[dict]:
    """Handles/aliases a page asserts, with provenance for each."""
    out: dict[str, str] = {}
    for match in re.finditer(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9._-]{2,30})", text):
        out.setdefault(match.group(1), "at-mention in page text")
    for url in links:
        slug = urlsplit(url).path.strip("/").split("/")[-1] if urlsplit(url).path else ""
        host = (urlsplit(url).hostname or "").casefold()
        if slug and len(slug) >= 5 and slug not in {
            "about",
            "blog",
            "posts",
            "projects",
            "contact",
            "portfolio",
            "feed",
            "rss",
            "atom",
            "cv",
            "resume",
            "tags",
            "archive",
        }:
            out.setdefault(slug, f"path segment on {host}")
    return [{"handle": h, "origin": why} for h, why in sorted(out.items())[:24]]


def _domain_candidates(links: list[str], known_platform_hosts: set[str]) -> list[str]:
    domains: set[str] = set()
    for url in links:
        host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
        if (
            host
            and "." in host
            and host not in known_platform_hosts
            and not any(j in host for j in _PLATFORM_JUNK)
            and not host.split(".")[-1] in {"css", "js"}
        ):
            domains.add(host)
    return sorted(domains)[:12]


async def read_source(
    url: str,
    http: Http,
    bus: Bus | None = None,
    *,
    via: str = "",
    subject: str = "",
) -> dict:
    """Fetch one page and extract what it publicly asserts."""
    fetch = await http.get(url, safe=True)
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found":
        record = source_record(
            url=url,
            outcome=fetch.outcome,
            via=via,
            error=fetch.error,
            retrieved_at=now,
            http_status=fetch.status,
        )
        if bus:
            await bus.emit("source", outcome=fetch.outcome, url=url, via=via)
        return {"source": record, "unavailable": True}

    body = fetch.text or ""
    is_json = body.lstrip()[:1] in {"{", "["}
    soup = BeautifulSoup(body, "lxml") if not is_json else None
    title = ""
    canonical = ""
    author = ""
    published = ""
    text = ""
    persons: list[dict] = []
    sitemap_urls: list[str] = []
    classified: dict[str, list[str]] = {"feeds": [], "rel_me": [], "documents": [], "images": [], "links": []}
    if soup is not None:
        _strip_junk(soup)
        if soup.title:
            title = soup.title.get_text(" ").strip()
        canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in v)
        if canonical_tag and canonical_tag.get("href"):
            canonical = urljoin(fetch.final_url or url, canonical_tag["href"])
        author_meta = soup.find("meta", attrs={"name": "author"}) or soup.find(
            "meta", attrs={"property": "article:author"}
        )
        if author_meta:
            author = (author_meta.get("content") or "").strip()
        published_meta = soup.find("meta", attrs={"property": "article:published_time"})
        if published_meta:
            published = (published_meta.get("content") or "").strip()[:40]
        text = _main_text(soup)
        persons = _jsonld_persons(soup)
        classified = classify_links(soup, fetch.final_url or url)
        sitemap_urls = [
            urljoin(fetch.final_url or url, loc.get_text(" ").strip())
            for loc in soup.find_all("loc")[:50]
            if loc.get_text(" ").strip()
        ]
    else:
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                text = json.dumps(data)[:_TEXT_CAP]
        except ValueError:
            text = body[:_TEXT_CAP]

    final_url = canonical or fetch.final_url or url
    record = source_record(
        url=url,
        outcome="found",
        final_url=final_url,
        title=title or str(urlsplit(final_url).netloc),
        content_type="html" if soup is not None else ("json" if is_json else "text"),
        via=via,
        excerpt=text[:500],
        retrieved_at=now,
        http_status=fetch.status,
        extra={
            "canonical": canonical,
            "author": author,
            "published": published,
            "persons": persons,
        },
    )
    mentions = find_mentions(text, subject, author=author) if subject else []
    known_platform_hosts = _platform_hosts()
    page = {
        "title": title,
        "text": text,
        "author": author,
        "published": published,
        "canonical": canonical,
        "persons": persons,
        "mentions": mentions,
        "handles": _handle_candidates(text, classified["links"] + classified["rel_me"]),
        "domains": _domain_candidates(classified["links"], known_platform_hosts),
        "sitemap_urls": sitemap_urls,
    }
    page.update(classified)
    if bus:
        await bus.emit(
            "source",
            outcome="found",
            url=final_url,
            title=title,
            via=via,
            chars=len(text),
            links=len(classified["links"]),
            mentions=len(mentions),
        )
    return {"source": record, "page": page}


def _platform_hosts() -> set[str]:
    from snoop.evidence import _is_platform_domain

    hosts: set[str] = set()
    try:
        from snoop.enum import _SITES

        for site in _SITES:
            host = (urlsplit(site["url"].replace("{}", "x")).hostname or "").lower()
            if host:
                hosts.add(host.removeprefix("www."))
                hosts.add(host)
    except Exception:
        pass
    _ = _is_platform_domain
    return hosts


async def crawl_site(
    start_url: str,
    http: Http,
    bus: Bus | None = None,
    *,
    via: str = "",
    subject: str = "",
    max_pages: int = 5,
) -> list[dict]:
    """Read the entry page plus the most relevant about/project/feed/sitemap pages."""
    results = []
    entry = await read_source(start_url, http, bus, via=via, subject=subject)
    results.append(entry)
    if entry.get("unavailable"):
        return results
    base = entry["source"]["url"]
    seen = {canonical_url(base)}
    candidates: list[tuple[float, str]] = []
    interesting = ("about", "project", "portfolio", "bio", "author", "person", "work", "cv", "resume")
    for link in entry["page"]["links"][:120]:
        host = (urlsplit(link).hostname or "").casefold()
        base_host = (urlsplit(base).hostname or "").casefold()
        if host != base_host:
            continue
        path = urlsplit(link).path.casefold()
        if any(word in path for word in interesting):
            candidates.append((2.0, link))
    for feed in entry["page"]["feeds"]:
        candidates.append((1.5, feed))
    sitemap = urljoin(base, "/sitemap.xml")
    candidates.append((1.0, sitemap))
    candidates.sort(key=lambda x: -x[0])
    pages_read = 1
    for _weight, url in candidates:
        if pages_read >= max_pages or canonical_url(url) in seen:
            continue
        seen.add(canonical_url(url))
        result = await read_source(url, http, bus, via=f"crawl:{canonical_url(base)}", subject=subject)
        results.append(result)
        pages_read += 1
        if url.endswith("sitemap.xml") and not result.get("unavailable"):
            from snoop.evidence import tokens as _tokens

            subject_tokens = _tokens(subject)
            for loc in result.get("page", {}).get("sitemap_urls", [])[:50]:
                if pages_read >= max_pages:
                    break
                slug = urlsplit(loc).path.casefold()
                if subject_tokens and any(t in slug for t in subject_tokens) and canonical_url(loc) not in seen:
                    seen.add(canonical_url(loc))
                    sub = await read_source(
                        loc, http, bus, via=f"sitemap:{canonical_url(url)}", subject=subject
                    )
                    results.append(sub)
                    pages_read += 1
    return results


# -------------------------------------------------------------------- documents


def _pdf_text_heuristic(raw: bytes) -> tuple[str, str, list[str], list[dict]]:
    """Dependency-free fallback: inflate streams and pull text operators."""
    author = ""
    m = re.search(rb"/Author\s*\(([^)]{0,200})\)", raw)
    if m:
        author = m.group(1).decode("latin-1", "ignore")
    urls = [u.decode("latin-1", "ignore") for u in re.findall(rb"/URI\s*\((https?://[^)]{1,300})\)", raw)]
    chunks: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        try:
            data = zlib.decompress(match.group(1).strip(b"\r\n"))
        except zlib.error:
            continue
        for literal in re.findall(rb"\((?:[^()\\]|\\.){1,500}\)\s*Tj", data):
            chunks.append(literal[1 : literal.rfind(b")")].decode("latin-1", "ignore"))
        for tj in re.findall(rb"\[(?:[^\[\]]|\\.)*\]\s*TJ", data):
            chunks.append(
                " ".join(
                    piece[1 : piece.rfind(b")")].decode("latin-1", "ignore")
                    for piece in re.findall(rb"\((?:[^()\\]|\\.)*\)", tj)
                )
            )
    text = re.sub(r"\s+", " ", " ".join(chunks)).strip()
    pages = (
        [
            {
                "page": None,
                "text": text[:5000],
                "excerpt": text[:500],
                "location": "page unavailable (fallback extractor)",
            }
        ]
        if text
        else []
    )
    return text, author, urls, pages


def _pdf_text_pypdf(raw: bytes) -> tuple[str, str, list[str], list[dict]]:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    meta = reader.metadata or {}
    pages: list[str] = []
    page_records: list[dict] = []
    urls: list[str] = []
    for page_no, page in enumerate(reader.pages, 1):
        if page_no > _PDF_PAGE_CAP or sum(map(len, pages)) >= _TEXT_CAP:
            break
        page_text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        pages.append(page_text)
        page_records.append(
            {
                "page": page_no,
                "text": page_text[:5000],
                "excerpt": page_text[:500],
                "location": f"page {page_no}",
            }
        )
        try:
            for annot in page.get("/Annots") or []:
                obj = annot.get_object()
                uri = (obj.get("/A") or {}).get("/URI") if obj.get("/A") else None
                if uri:
                    urls.append(str(uri))
        except Exception:
            continue
    author = str(meta.get("/Author", "") or "")
    return "\n".join(pages), author, urls, page_records


def _pdf_worker(raw: bytes, sender) -> None:
    """Run every PDF parser outside the web server process."""
    try:
        try:
            result = _pdf_text_pypdf(raw)
            method = "pypdf-bounded"
        except BaseException:
            # Even the conservative regex fallback is isolated: malformed
            # compressed streams can otherwise monopolise the event loop.
            result = _pdf_text_heuristic(raw)
            method = "pdf-heuristic"
        sender.send((True, (result, method)))
    except BaseException as exc:
        sender.send((False, f"{type(exc).__name__}: {str(exc)[:160]}"))
    finally:
        sender.close()


async def _pdf_text_bounded(
    raw: bytes,
) -> tuple[tuple[tuple[str, str, list[str], list[dict]], str] | None, str]:
    """Extract a PDF without letting malformed input freeze the event loop.

    pypdf operates in a short-lived process because cancelling an asyncio task
    cannot interrupt CPU-bound Python parsing. The worker can be terminated on
    timeout, leaving the server responsive and the investigation free to move
    to its next lead.
    """
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_pdf_worker, args=(raw, sender), daemon=True)
    started = False
    try:
        process.start()
        started = True
        sender.close()
        deadline = asyncio.get_running_loop().time() + max(1.0, config.document_parse_timeout)
        while asyncio.get_running_loop().time() < deadline:
            if receiver.poll():
                ok, payload = receiver.recv()
                return (payload, "") if ok else (None, str(payload))
            if not process.is_alive():
                break
            await asyncio.sleep(0.05)
        return None, "document parser timed out"
    except (OSError, RuntimeError, EOFError) as exc:
        return None, f"document parser unavailable: {type(exc).__name__}"
    finally:
        if started and process.is_alive():
            process.terminate()
        if started:
            await asyncio.to_thread(process.join, 1.0)
        receiver.close()
        if started and process.exitcode is not None:
            process.close()


async def read_document(url: str, http: Http, bus: Bus | None = None, *, via: str = "") -> dict:
    """Fetch a public document and extract text, author fields and links."""
    fetch = await http.get(url, safe=True, want_bytes=True)
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found":
        record = source_record(
            url=url, outcome=fetch.outcome, via=via, error=fetch.error, retrieved_at=now
        )
        return {"source": record, "unavailable": True}
    raw = fetch.raw or b""
    is_pdf = raw[:5] == b"%PDF-" or url.casefold().endswith(".pdf")
    text = author = ""
    urls: list[str] = []
    pages: list[dict] = []
    method = "none"
    if is_pdf:
        parsed, parse_error = await _pdf_text_bounded(raw)
        if parsed is not None:
            extracted, method = parsed
            text, author, urls, pages = extracted
        else:
            # Do not retry unsafe parser work on the event loop. Preserve the
            # source and state the limitation; the workflow will continue.
            text = author = ""
            urls, pages = [], []
            method = "pdf-timeout" if "timed out" in parse_error else "pdf-unavailable"
    else:
        text = raw[:200000].decode("utf-8", "ignore")
        method = "plain-text"
        pages = [
            {
                "page": 1,
                "text": text[:5000],
                "excerpt": text[:500],
                "location": "document text",
            }
        ]
    text = re.sub(r"\s+", " ", text).strip()[:_TEXT_CAP]
    status = "read"
    if is_pdf and len(text) < 60:
        status = "needs_ocr"
    record = source_record(
        url=url,
        outcome="found",
        final_url=fetch.final_url or url,
        title=(urlsplit(url).path.rsplit("/", 1)[-1] or url),
        content_type="pdf" if is_pdf else "document",
        via=via,
        excerpt=text[:500],
        retrieved_at=now,
        http_status=fetch.status,
        extra={
            "document_status": status,
            "extraction": method,
            "author": author,
            "urls": sorted(set(urls))[:30],
            "text_chars": len(text),
            "page_citations": [
                {
                    "page": page.get("page"),
                    "location": page.get("location", ""),
                    "excerpt": page.get("excerpt", "")[:500],
                }
                for page in pages[:100]
            ],
        },
    )
    if bus:
        await bus.emit(
            "document",
            url=url,
            status=status,
            method=method,
            chars=len(text),
            author=author,
        )
    return {
        "source": record,
        "text": text,
        "author": author,
        "urls": sorted(set(urls))[:30],
        "pages": pages[:100],
        "status": status,
        "method": method,
    }


# ---------------------------------------------------------------------- archive


async def wayback_availability(url: str, http: Http) -> dict:
    fetch = await http.get(
        "https://archive.org/wayback/available?url=" + quote(url, safe=""),
        want_json=True,
        credentials_for="archive.org",
    )
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found" or not isinstance(fetch.json, dict):
        return {"url": url, "outcome": fetch.outcome, "retrieved_at": now}
    snapshot = ((fetch.json.get("archived_snapshots") or {}).get("closest") or {})
    return {
        "url": url,
        "outcome": "found" if snapshot else "empty",
        "available": bool(snapshot.get("available")),
        "snapshot_url": snapshot.get("url", ""),
        # Keep capture time separate from retrieval time.
        "capture_timestamp": snapshot.get("timestamp", ""),
        "retrieved_at": now,
    }


async def wayback_cdx(url: str, http: Http, *, limit: int = 6) -> dict:
    fetch = await http.get(
        "https://web.archive.org/cdx/search/cdx?url="
        + quote(url, safe="")
        + f"&output=json&limit={max(1, min(limit, 20))}&collapse=digest",
        want_json=True,
        credentials_for="web.archive.org",
    )
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found" or not isinstance(fetch.json, list) or len(fetch.json) < 2:
        return {"url": url, "outcome": fetch.outcome if fetch.outcome != "found" else "empty", "captures": [], "retrieved_at": now}
    header, *rows = fetch.json
    captures = [dict(zip(header, row)) for row in rows]
    return {
        "url": url,
        "outcome": "found",
        "captures": [
            {
                "original": c.get("original", ""),
                "capture_timestamp": c.get("timestamp", ""),
                "capture_url": f"https://web.archive.org/web/{c.get('timestamp', '')}/{c.get('original', '')}",
                "statuscode": c.get("statuscode", ""),
                "mimetype": c.get("mimetype", ""),
            }
            for c in captures
        ],
        "retrieved_at": now,
    }


async def common_crawl_lookup(url_or_domain: str, http: Http, *, limit: int = 10) -> dict:
    """Bounded URL-index lookup. This is not a free-text search engine for names."""
    index = config.common_crawl_index
    fetch = await http.get(
        f"https://index.commoncrawl.org/{index}-url?url=" + quote(url_or_domain, safe="*") + f"&output=json&limit={limit}",
        want_json=True,
        credentials_for="index.commoncrawl.org",
    )
    now = fetch.retrieved_at or utcnow()
    rows = []
    if fetch.outcome == "found" and fetch.text:
        for line in fetch.text.splitlines()[:limit]:
            try:
                row = json.loads(line)
                rows.append(
                    {
                        "url": row.get("url", ""),
                        "capture_timestamp": row.get("timestamp", ""),
                        "status": str(row.get("status", "")),
                    }
                )
            except ValueError:
                continue
    return {
        "query": url_or_domain,
        "index": index,
        "outcome": fetch.outcome if fetch.outcome != "found" else ("found" if rows else "empty"),
        "urls": rows,
        "retrieved_at": now,
    }


# ----------------------------------------------------------------------- domain


async def rdap_domain(domain: str, http: Http) -> dict:
    fetch = await http.get(
        "https://rdap.org/domain/" + quote(domain, safe=""), want_json=True, credentials_for="rdap.org"
    )
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found" or not isinstance(fetch.json, dict):
        return {"domain": domain, "outcome": fetch.outcome, "retrieved_at": now}
    data = fetch.json
    events = {e.get("eventAction", ""): e.get("eventDate", "") for e in data.get("events", []) if isinstance(e, dict)}
    registrar = ""
    for entity in data.get("entities", []):
        roles = entity.get("roles") or []
        if "registrar" in roles:
            registrar = str((entity.get("vcardArray") or [None, []])[1]).strip("[]'")
            break
    return {
        "domain": domain,
        "outcome": "found",
        "registered": events.get("registration", ""),
        "expires": events.get("expiration", ""),
        "changed": events.get("last changed", ""),
        "registrar": registrar[:120],
        "nameservers": [ns.get("ldhName", "") for ns in data.get("nameservers", [])][:8],
        "status": data.get("status", [])[:6],
        "retrieved_at": now,
    }


async def dns_addresses(domain: str) -> dict:
    try:
        loop = asyncio.get_running_loop()
        rows = await loop.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
        addresses = sorted({row[4][0] for row in rows})
        return {"domain": domain, "outcome": "found", "addresses": addresses[:12], "retrieved_at": utcnow()}
    except (socket.gaierror, OSError) as exc:
        return {"domain": domain, "outcome": "unavailable", "error": str(exc)[:160], "retrieved_at": utcnow()}


async def ct_certificates(domain: str, http: Http, *, limit: int = 20) -> dict:
    fetch = await http.get(
        "https://crt.sh/?q=" + quote("%." + domain, safe="") + f"&output=json&limit={limit}",
        want_json=True,
        credentials_for="crt.sh",
        safe=True,
    )
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found" or not isinstance(fetch.json, list):
        return {"domain": domain, "outcome": fetch.outcome, "retrieved_at": now}
    certs = [
        {
            "common_name": row.get("common_name", ""),
            "names": (row.get("name_value", "") or "").replace("\n", " ")[:300],
            "issuer": (row.get("issuer_name", "") or "")[:160],
            "not_before": row.get("not_before", ""),
            "not_after": row.get("not_after", ""),
        }
        for row in fetch.json
        if isinstance(row, dict)
    ][:limit]
    return {"domain": domain, "outcome": "found", "certificates": certs, "retrieved_at": now}


# ----------------------------------------------------------------------- image


def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True


async def image_clues(url: str, http: Http, *, reverse: bool = False) -> dict:
    """Read text/handles/URLs out of an image; reverse-image only when explicit."""
    fetch = await http.get(url, safe=True, want_bytes=True, max_bytes=8_000_000)
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found":
        return {"url": url, "outcome": fetch.outcome, "retrieved_at": now}
    result: dict = {
        "url": url,
        "outcome": "found",
        "ocr": "unavailable",
        "text": "",
        "handles": [],
        "urls": [],
        "retrieved_at": now,
    }
    if ocr_available():
        try:
            import io

            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(fetch.raw))
            text = pytesseract.image_to_string(image) or ""
            result["ocr"] = "read"
            result["text"] = re.sub(r"\s+", " ", text).strip()[:2000]
            result["handles"] = [
                m.group(1)
                for m in re.finditer(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9._-]{2,30})", text)
            ][:12]
            result["urls"] = re.findall(r"https?://[^\s\"'<>]+", text)[:12]
        except Exception as exc:
            result["ocr"] = f"failed: {type(exc).__name__}"
    else:
        result["ocr"] = (
            "not installed; install optional dependencies pytesseract and Pillow "
            "(plus the Tesseract binary) for image OCR"
        )
    if reverse and config.serpapi_key:
        result["reverse_image"] = await _google_lens(url, http)
    elif reverse:
        result["reverse_image"] = {
            "outcome": "missing_key",
            "error": "reverse image search needs SERPAPI_KEY (Google Lens)",
        }
    return result


async def _google_lens(url: str, http: Http) -> dict:
    from urllib.parse import urlencode

    params = {"engine": "google_lens", "image_url": url, "api_key": config.serpapi_key}
    fetch = await http.get(
        "https://serpapi.com/search.json?" + urlencode(params),
        want_json=True,
        credentials_for="serpapi.com",
    )
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found" or not isinstance(fetch.json, dict):
        return {"outcome": fetch.outcome, "error": fetch.error, "retrieved_at": now}
    matches = [
        {
            "title": str(m.get("title", ""))[:200],
            "url": m.get("link", ""),
            "source": m.get("source", ""),
        }
        for m in fetch.json.get("visual_matches", [])
        if isinstance(m, dict) and m.get("link")
    ][:15]
    return {
        "outcome": "found" if matches else "empty",
        "engine": "Google Lens via SerpAPI",
        "matches": matches,
        "retrieved_at": now,
    }
