"""Shared data models for Numint.

These pydantic models are the single contract passed between the parser,
providers, aggregator, footprint layer, AI layer, CLI and web UI. No layer
defines its own ad-hoc dict shape; everything flows through here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NumberType(str, Enum):
    """Normalized line/number type across providers and libphonenumber."""

    MOBILE = "mobile"
    FIXED_LINE = "fixed_line"
    FIXED_OR_MOBILE = "fixed_or_mobile"
    VOIP = "voip"
    TOLL_FREE = "toll_free"
    PREMIUM_RATE = "premium_rate"
    SHARED_COST = "shared_cost"
    PERSONAL = "personal"
    PAGER = "pager"
    UAN = "uan"
    VOICEMAIL = "voicemail"
    UNKNOWN = "unknown"


class ParsedNumber(BaseModel):
    """Result of offline parsing with `phonenumbers`. Passed to every provider."""

    raw: str
    e164: str
    national: str
    international: str
    rfc3966: str
    country_code: int
    country_iso: str | None = None
    country_name: str | None = None
    region: str | None = None
    is_valid: bool = False
    is_possible: bool = False
    number_type: NumberType = NumberType.UNKNOWN
    carrier: str | None = None
    timezones: list[str] = Field(default_factory=list)

    @property
    def digits(self) -> str:
        """E.164 without the leading '+', useful for URL templates."""
        return self.e164.lstrip("+")


class Attribute(BaseModel):
    """A single value paired with the provider that reported it.

    The aggregator keeps every source's opinion rather than collapsing to one,
    so conflicts stay visible and confidence can be computed.
    """

    value: Any
    source: str


class ProviderStatus(str, Enum):
    RAN = "ran"
    SKIPPED = "skipped"  # not configured (no key)
    ERROR = "error"


class ProviderResult(BaseModel):
    """Normalized envelope returned by every provider's `lookup`."""

    source: str
    ok: bool = False
    status: ProviderStatus = ProviderStatus.RAN
    raw: dict[str, Any] | None = None
    mapped: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    elapsed_ms: int | None = None


class ProviderReport(BaseModel):
    """Per-provider audit line shown in the `providers` block of the output."""

    name: str
    status: ProviderStatus
    requires_key: bool
    reason: str | None = None
    elapsed_ms: int | None = None


class RiskProfile(BaseModel):
    fraud_score: Attribute | None = None  # 0-100 where higher = riskier
    spam: Attribute | None = None
    disposable: Attribute | None = None
    voip: Attribute | None = None
    active: Attribute | None = None
    recent_abuse: Attribute | None = None


class PresenceResult(BaseModel):
    """Account-presence check for one site.

    Answers "is this number registered here?" by reading a site's own
    signup/reset/lookup response - never by logging in. `registered` is a
    coarse signal; `masked_*` capture any partial identifier the site leaks
    (e.g. `j••@gm***.com`) so an investigator can pivot.
    """

    site: str
    registered: str = "unknown"  # yes | no | unknown | rate_limited | error
    masked_email: str | None = None
    masked_phone: str | None = None
    hint: str | None = None  # username / display-name fragment
    method: str = "lookup"  # lookup | reset | signup - audit trail
    elapsed_ms: int | None = None
    error: str | None = None


class FootprintLink(BaseModel):
    label: str
    url: str


class FootprintGroup(BaseModel):
    category: str
    links: list[FootprintLink] = Field(default_factory=list)


class AIAnalysis(BaseModel):
    provider: str
    model: str
    summary: str | None = None
    conflicts: str | None = None
    risk_read: str | None = None
    next_steps: str | None = None
    answer: str | None = None  # populated only for --ask
    error: str | None = None


class Profile(BaseModel):
    """The unified intelligence profile - the single output object."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    input: ParsedNumber

    # Merged / multi-source attributes (each keeps its source tags).
    carriers: list[Attribute] = Field(default_factory=list)
    line_types: list[Attribute] = Field(default_factory=list)
    locations: list[Attribute] = Field(default_factory=list)
    countries: list[Attribute] = Field(default_factory=list)
    validity: list[Attribute] = Field(default_factory=list)

    risk: RiskProfile = Field(default_factory=RiskProfile)
    presence: list[PresenceResult] = Field(default_factory=list)
    footprint: list[FootprintGroup] = Field(default_factory=list)
    dorking: list[FootprintGroup] = Field(default_factory=list)
    sites: list[FootprintGroup] = Field(default_factory=list)
    providers: list[ProviderReport] = Field(default_factory=list)
    ai_analysis: AIAnalysis | None = None

    # Confidence signal: agreement counts keyed by field name.
    confidence: dict[str, dict[str, int]] = Field(default_factory=dict)

    def primary_carrier(self) -> str | None:
        return _most_common([a.value for a in self.carriers])

    def primary_line_type(self) -> str | None:
        return _most_common([a.value for a in self.line_types])


def _most_common(values: list[Any]) -> Any | None:
    cleaned = [v for v in values if v]
    if not cleaned:
        return None
    counts: dict[Any, int] = {}
    for v in cleaned:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get)
