"""Acuity JSON schema — the contract between source agents, the synthesis
agent, the backend API, and the frontend.

**Locked at H1 (JOINT-01).** Any change after H4 requires both teammates to
agree (CLAUDE.md hard rule).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- #
# Shared vocabulary
# --------------------------------------------------------------------------- #

class Severity(str, Enum):
    """Final synthesized severity. Used by the synthesis agent and report."""

    CONTRAINDICATED = "contraindicated"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NO_CONCERN = "no_concern"


class SeverityHint(str, Enum):
    """What a single source says before reconciliation. Narrower vocabulary."""

    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"


class Coverage(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    NO_DATA = "no_data"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


SourceName = Literal["openfda_label", "openfda_faers", "twosides"]
FindingType = Literal["interaction", "adverse_event", "predicted_effect"]


# --------------------------------------------------------------------------- #
# Drug normalization
# --------------------------------------------------------------------------- #

class NormalizedDrug(BaseModel):
    """Result of RxNorm normalization. Produced by BE-04."""

    model_config = ConfigDict(extra="forbid")

    input_name: str = Field(..., description="Free-text input from the user.")
    rxcui: Optional[str] = Field(None, description="RxNorm Concept Unique Identifier; None if unresolved.")
    generic_name: Optional[str] = Field(None, description="Canonical ingredient name (TTY=IN).")
    brand_names: list[str] = Field(default_factory=list)
    found: bool = Field(..., description="True iff RxNorm resolved the input.")


class DrugPair(BaseModel):
    """An unordered pair of normalized drugs. Equality is order-independent."""

    model_config = ConfigDict(extra="forbid")

    a: NormalizedDrug
    b: NormalizedDrug

    @property
    def key(self) -> tuple[str, str]:
        """Stable, order-independent identity for caching/memory."""
        names = sorted([self.a.generic_name or self.a.input_name,
                        self.b.generic_name or self.b.input_name])
        return (names[0], names[1])


# --------------------------------------------------------------------------- #
# Source-agent output
# --------------------------------------------------------------------------- #

class Evidence(BaseModel):
    """Per-finding evidence. All fields source-dependent and optional."""

    model_config = ConfigDict(extra="forbid")

    raw_excerpt: Optional[str] = Field(None, description="Verbatim text from the source.")
    frequency: Optional[float] = Field(None, description="Observed frequency / co-report count.")
    probability: Optional[float] = Field(None, description="Source-reported probability or PRR.")
    source_url: Optional[str] = Field(None, description="Permalink to the underlying record.")


class Finding(BaseModel):
    """A single signal from one source about one drug pair."""

    model_config = ConfigDict(extra="forbid")

    type: FindingType
    description: str
    severity_hint: Optional[SeverityHint] = Field(
        None,
        description="What the source itself implies about severity. Not the final synthesized severity.",
    )
    evidence: Evidence = Field(default_factory=Evidence)


class SourceFindings(BaseModel):
    """Output of one source agent for one drug pair.

    `coverage == NO_DATA` is meaningful — synthesis must distinguish "absent
    signal" from "absence of evidence", and may not assume safety when sources
    are silent.
    """

    model_config = ConfigDict(extra="forbid")

    source: SourceName
    drug_pair: tuple[str, str] = Field(
        ..., description="Pair of normalized drug names (lowercase, sorted)."
    )
    queried_at: datetime
    findings: list[Finding] = Field(default_factory=list)
    coverage: Coverage
    confidence: Confidence

    @field_validator("drug_pair")
    @classmethod
    def _normalize_pair(cls, v: tuple[str, str]) -> tuple[str, str]:
        if len(v) != 2:
            raise ValueError("drug_pair must contain exactly two names")
        a, b = (s.strip().lower() for s in v)
        return tuple(sorted([a, b]))  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Synthesis-agent output
# --------------------------------------------------------------------------- #

class Citation(BaseModel):
    """Pointer back into a SourceFindings.findings[] entry."""

    model_config = ConfigDict(extra="forbid")

    source: SourceName
    finding_index: int = Field(..., ge=0, description="Index into SourceFindings.findings[].")
    quote: str = Field(..., description="Short verbatim excerpt the model relied on.")


class SynthesizedInteraction(BaseModel):
    """The synthesis agent's verdict on one drug pair."""

    model_config = ConfigDict(extra="forbid")

    drug_pair: tuple[str, str]
    severity: Severity
    headline: str = Field(..., description="One-sentence summary for the report header.")
    reasoning: str = Field(
        ...,
        description=(
            "Chain-of-thought trace. MUST explicitly address source agreement "
            "or disagreement when multiple sources weighed in."
        ),
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Mandatory if severity != no_concern.",
    )
    predicted_but_unverified: bool = Field(
        False,
        description="True when at least one source flags risk and at least one finds nothing.",
    )
    sources_agreement: Literal["agree", "disagree", "single_source", "no_data"] = "no_data"


class RegimenReport(BaseModel):
    """The full output for one query. Versioned for the API contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    regimen: list[NormalizedDrug]
    generated_at: datetime
    overall_summary: str
    interactions: list[SynthesizedInteraction] = Field(
        default_factory=list,
        description="Sorted by severity (contraindicated→major→moderate→minor→no_concern).",
    )
    new_pairs: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Pairs newly evaluated since the previous regimen snapshot.",
    )
    cached_pairs: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Pairs reused from memory.",
    )
    patient_friendly_summary: Optional[str] = Field(
        None, description="Plain-language version of overall_summary."
    )
    sources_consulted: list[str] = Field(
        default_factory=list,
        description="Unique source names that returned data for at least one pair.",
    )


# --------------------------------------------------------------------------- #
# Deep-research schema (added for skills/deep_research)
# --------------------------------------------------------------------------- #

class ResearchCitation(BaseModel):
    """A URL-backed citation from a Brave search result."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    quote: Optional[str] = Field(None, description="Relevant excerpt from the page.")


class DeepResearchFinding(BaseModel):
    """One researched aspect of a drug."""

    model_config = ConfigDict(extra="forbid")

    aspect: Literal[
        "mechanism",
        "indications",
        "contraindications",
        "adverse_events",
        "interactions",
        "pharmacokinetics",
        "other",
    ]
    summary: str = Field(..., description="Synthesized summary for this aspect.")
    citations: list[ResearchCitation] = Field(default_factory=list)


class DeepResearchReport(BaseModel):
    """Output of the DeepResearch skill for a single drug."""

    model_config = ConfigDict(extra="forbid")

    report_type: Literal["deep_research"] = "deep_research"
    schema_version: Literal["1.0"] = "1.0"
    drug: str = Field(..., description="Drug name as provided by the user.")
    generated_at: datetime
    executive_summary: str = Field(..., description="Two-to-four sentence overview.")
    findings: list[DeepResearchFinding] = Field(
        default_factory=list,
        description="One entry per researched aspect.",
    )


# --------------------------------------------------------------------------- #
# User-data schemas (used by /api/user/* routes)
# --------------------------------------------------------------------------- #

class ProfileOut(BaseModel):
    """Public view of a user profile row."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    age: Optional[int] = None
    sex: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    doctor: Optional[str] = None
    doctor_email: Optional[str] = None


class RegimenEntry(BaseModel):
    """One row from the regimen table (active medications)."""

    model_config = ConfigDict(extra="allow")

    id: str
    profile_id: str
    input_name: str
    rxcui: Optional[str] = None
    generic_name: Optional[str] = None
    brand_names: list[str] = Field(default_factory=list)
    dose: Optional[str] = None
    frequency: Optional[str] = None
    found: bool = False
    added_at: Optional[datetime] = None
    removed_at: Optional[datetime] = None


class SessionSummary(BaseModel):
    """Lightweight summary of a past analysis session."""

    model_config = ConfigDict(extra="allow")

    id: str
    new_drug: Optional[str] = None
    drugs_checked: list[str] = Field(default_factory=list)
    overall_severity: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class InteractionRow(BaseModel):
    """One row from the interactions table."""

    model_config = ConfigDict(extra="allow")

    id: str
    session_id: str
    drug_a: str
    drug_b: str
    severity: str
    headline: str
    reasoning: Optional[str] = None
    sources_agreement: Optional[str] = None
    predicted_but_unverified: bool = False
    citations: list[dict] = Field(default_factory=list)
    sort_order: int = 0


__all__ = [
    "Citation",
    "Confidence",
    "Coverage",
    "DeepResearchFinding",
    "DeepResearchReport",
    "DrugPair",
    "Evidence",
    "Finding",
    "FindingType",
    "InteractionRow",
    "NormalizedDrug",
    "ProfileOut",
    "RegimenEntry",
    "RegimenReport",
    "ResearchCitation",
    "SessionSummary",
    "Severity",
    "SeverityHint",
    "SourceFindings",
    "SourceName",
    "SynthesizedInteraction",
]
