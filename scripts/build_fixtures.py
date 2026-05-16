"""Generate samples/fixtures.json — 9 SourceFindings (3 sources × 3 pairs)
plus one full RegimenReport, so the frontend (FE-01+) can render without a
backend.

JOINT-01 acceptance: this file exists with realistic data.

# TODO(synthetic-data): every value below — the FAERS counts, the PRR
# numbers, the synthesis reasoning paragraphs, the citation quotes — is
# hand-authored, not captured from a live pipeline run. The structure
# matches the schema and the clinical content is plausible, but it is NOT
# the output of /api/analyze. Before any judge-facing demo, replace this
# with a captured RegimenReport from a real pipeline run, e.g.:
#     curl -X POST .../api/analyze -d '{"drugs":["warfarin","aspirin",...]}'
#       > samples/fixtures_live.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.schemas import (  # noqa: E402
    Citation,
    Confidence,
    Coverage,
    Evidence,
    Finding,
    NormalizedDrug,
    RegimenReport,
    Severity,
    SeverityHint,
    SourceFindings,
    SynthesizedInteraction,
)

NOW = datetime(2026, 5, 16, 4, 30, tzinfo=timezone.utc)
OUT = Path(__file__).resolve().parent.parent / "samples" / "fixtures.json"


def drug(name: str, rxcui: str, brands: list[str] | None = None) -> NormalizedDrug:
    return NormalizedDrug(
        input_name=name,
        rxcui=rxcui,
        generic_name=name.lower(),
        brand_names=brands or [],
        found=True,
    )


WARFARIN = drug("warfarin", "11289", brands=["Coumadin", "Jantoven"])
ASPIRIN = drug("aspirin", "1191", brands=["Bayer", "Ecotrin"])
FLUOXETINE = drug("fluoxetine", "4493", brands=["Prozac"])
TRAMADOL = drug("tramadol", "10689", brands=["Ultram"])
METFORMIN = drug("metformin", "6809", brands=["Glucophage"])
LISINOPRIL = drug("lisinopril", "29046", brands=["Prinivil", "Zestril"])

# --------------------------------------------------------------------------- #
# Source findings — 3 pairs, 3 sources each
# --------------------------------------------------------------------------- #

label_warfarin_aspirin = SourceFindings(
    source="openfda_label",
    drug_pair=("warfarin", "aspirin"),
    queried_at=NOW,
    coverage=Coverage.FULL,
    confidence=Confidence.HIGH,
    findings=[
        Finding(
            type="interaction",
            description="Concomitant aspirin increases risk of major and fatal bleeding when given with warfarin.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(
                raw_excerpt=(
                    "WARNING: BLEEDING RISK — Warfarin sodium can cause major or fatal "
                    "bleeding. Concomitant use of aspirin and NSAIDs increases this risk."
                ),
                source_url="https://api.fda.gov/drug/label.json?search=openfda.generic_name:warfarin",
            ),
        ),
        Finding(
            type="interaction",
            description="Boxed warning explicitly lists antiplatelet drugs as bleeding-risk modifiers.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(
                raw_excerpt="Drugs that affect haemostasis (e.g., aspirin) may increase bleeding risk.",
            ),
        ),
    ],
)

faers_warfarin_aspirin = SourceFindings(
    source="openfda_faers",
    drug_pair=("warfarin", "aspirin"),
    queried_at=NOW,
    coverage=Coverage.FULL,
    confidence=Confidence.HIGH,
    findings=[
        Finding(
            type="adverse_event",
            description="Gastrointestinal haemorrhage co-reported in 1,842 cases.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(
                raw_excerpt="Top co-reported reaction across cases listing both warfarin and aspirin.",
                frequency=1842,
                source_url="https://api.fda.gov/drug/event.json?search=patient.drug.openfda.generic_name:warfarin+AND+patient.drug.openfda.generic_name:aspirin",
            ),
        ),
        Finding(
            type="adverse_event",
            description="Intracranial haemorrhage co-reported in 128 cases.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(frequency=128),
        ),
    ],
)

twosides_warfarin_aspirin = SourceFindings(
    source="twosides",
    drug_pair=("warfarin", "aspirin"),
    queried_at=NOW,
    coverage=Coverage.FULL,
    confidence=Confidence.HIGH,
    findings=[
        Finding(
            type="predicted_effect",
            description="Gastrointestinal haemorrhage PRR=6.41 — strong signal vs background.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(probability=6.41, frequency=1842),
        ),
        Finding(
            type="predicted_effect",
            description="Epistaxis PRR=4.11.",
            severity_hint=SeverityHint.MODERATE,
            evidence=Evidence(probability=4.11, frequency=498),
        ),
    ],
)

label_fluox_tram = SourceFindings(
    source="openfda_label",
    drug_pair=("fluoxetine", "tramadol"),
    queried_at=NOW,
    coverage=Coverage.PARTIAL,
    confidence=Confidence.MEDIUM,
    findings=[
        Finding(
            type="interaction",
            description="Use of tramadol with SSRIs increases risk of serotonin syndrome.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(
                raw_excerpt=(
                    "Cases of serotonin syndrome have been reported with concurrent use of "
                    "tramadol and serotonergic drugs including SSRIs."
                ),
            ),
        ),
    ],
)

faers_fluox_tram = SourceFindings(
    source="openfda_faers",
    drug_pair=("fluoxetine", "tramadol"),
    queried_at=NOW,
    coverage=Coverage.FULL,
    confidence=Confidence.MEDIUM,
    findings=[
        Finding(
            type="adverse_event",
            description="Serotonin syndrome co-reported in 412 cases.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(frequency=412),
        ),
        Finding(
            type="adverse_event",
            description="Seizure co-reported in 188 cases — secondary signal.",
            severity_hint=SeverityHint.MODERATE,
            evidence=Evidence(frequency=188),
        ),
    ],
)

twosides_fluox_tram = SourceFindings(
    source="twosides",
    drug_pair=("fluoxetine", "tramadol"),
    queried_at=NOW,
    coverage=Coverage.FULL,
    confidence=Confidence.HIGH,
    findings=[
        Finding(
            type="predicted_effect",
            description="Serotonin syndrome PRR=8.81 — very strong signal.",
            severity_hint=SeverityHint.MAJOR,
            evidence=Evidence(probability=8.81, frequency=412),
        ),
    ],
)

label_met_lis = SourceFindings(
    source="openfda_label",
    drug_pair=("metformin", "lisinopril"),
    queried_at=NOW,
    coverage=Coverage.PARTIAL,
    confidence=Confidence.LOW,
    findings=[
        Finding(
            type="interaction",
            description="ACE inhibitors may potentiate hypoglycaemia in metformin-treated patients.",
            severity_hint=SeverityHint.MINOR,
            evidence=Evidence(
                raw_excerpt="Concomitant use of ACE inhibitors with antidiabetics may rarely cause symptomatic hypoglycaemia."
            ),
        ),
    ],
)

faers_met_lis = SourceFindings(
    source="openfda_faers",
    drug_pair=("metformin", "lisinopril"),
    queried_at=NOW,
    coverage=Coverage.FULL,
    confidence=Confidence.MEDIUM,
    findings=[
        Finding(
            type="adverse_event",
            description="Hypoglycaemia co-reported in 312 cases.",
            severity_hint=SeverityHint.MINOR,
            evidence=Evidence(frequency=312),
        ),
    ],
)

twosides_met_lis = SourceFindings(
    source="twosides",
    drug_pair=("metformin", "lisinopril"),
    queried_at=NOW,
    coverage=Coverage.FULL,
    confidence=Confidence.MEDIUM,
    findings=[
        Finding(
            type="predicted_effect",
            description="Hypoglycaemia PRR=1.92 — modest signal.",
            severity_hint=SeverityHint.MINOR,
            evidence=Evidence(probability=1.92, frequency=312),
        ),
    ],
)

# --------------------------------------------------------------------------- #
# Sample synthesized report
# --------------------------------------------------------------------------- #

synth_warfarin_aspirin = SynthesizedInteraction(
    drug_pair=("warfarin", "aspirin"),
    severity=Severity.MAJOR,
    headline="High risk of major or fatal bleeding when warfarin and aspirin are used together.",
    reasoning=(
        "All three sources converge. OpenFDA's boxed warning on warfarin explicitly "
        "lists antiplatelets like aspirin as bleeding-risk modifiers. FAERS shows 1,842 "
        "co-reported GI haemorrhage cases and 128 intracranial bleeds for this pair, "
        "which is the dominant adverse-event signal. TWOSIDES corroborates with PRR=6.41 "
        "for GI haemorrhage. No source disagrees. Severity locked at MAJOR."
    ),
    citations=[
        Citation(source="openfda_label", finding_index=0, quote="Concomitant use of aspirin and NSAIDs increases this risk."),
        Citation(source="openfda_faers", finding_index=0, quote="1,842 cases of gastrointestinal haemorrhage."),
        Citation(source="twosides", finding_index=0, quote="PRR=6.41 for GI haemorrhage."),
    ],
    sources_agreement="agree",
)

synth_fluox_tram = SynthesizedInteraction(
    drug_pair=("fluoxetine", "tramadol"),
    severity=Severity.MAJOR,
    headline="Serotonin syndrome risk: concurrent SSRI + tramadol is an established cause.",
    reasoning=(
        "Label explicitly cites SSRI + tramadol as a serotonin-syndrome risk pairing. "
        "FAERS shows 412 serotonin-syndrome co-reports and TWOSIDES PRR=8.81 — among "
        "the highest signals in the dataset. All three sources agree."
    ),
    citations=[
        Citation(source="openfda_label", finding_index=0, quote="Cases of serotonin syndrome have been reported."),
        Citation(source="openfda_faers", finding_index=0, quote="412 cases of serotonin syndrome."),
        Citation(source="twosides", finding_index=0, quote="PRR=8.81."),
    ],
    sources_agreement="agree",
)

synth_met_lis = SynthesizedInteraction(
    drug_pair=("metformin", "lisinopril"),
    severity=Severity.MINOR,
    headline="Mild hypoglycaemia risk; commonly co-prescribed in diabetes with hypertension.",
    reasoning=(
        "Label flags a rare hypoglycaemia interaction. FAERS shows 312 hypoglycaemia "
        "co-reports — non-trivial but expected given how often these two are paired. "
        "TWOSIDES PRR=1.92 sits just above the noise floor. All sources weakly agree; "
        "severity is MINOR with routine monitoring sufficient."
    ),
    citations=[
        Citation(source="openfda_label", finding_index=0, quote="ACE inhibitors may potentiate hypoglycaemia."),
        Citation(source="twosides", finding_index=0, quote="PRR=1.92."),
    ],
    sources_agreement="agree",
)

report = RegimenReport(
    regimen=[WARFARIN, ASPIRIN, FLUOXETINE, TRAMADOL, METFORMIN, LISINOPRIL],
    generated_at=NOW,
    overall_summary=(
        "Two major interactions and one minor flagged across 15 evaluated pairs. "
        "Warfarin + aspirin and fluoxetine + tramadol both require intervention; "
        "metformin + lisinopril is acceptable with routine monitoring."
    ),
    interactions=[synth_warfarin_aspirin, synth_fluox_tram, synth_met_lis],
    new_pairs=[("warfarin", "aspirin"), ("fluoxetine", "tramadol"), ("metformin", "lisinopril")],
    cached_pairs=[],
    patient_friendly_summary=(
        "Two of your medication pairings need attention. Aspirin and warfarin together "
        "raise your risk of serious bleeding. Prozac and tramadol together can cause a "
        "rare but dangerous reaction called serotonin syndrome. Your metformin and "
        "lisinopril combination is mostly safe with normal check-ins."
    ),
)


def main() -> None:
    payload = {
        "source_findings": [
            label_warfarin_aspirin.model_dump(mode="json"),
            faers_warfarin_aspirin.model_dump(mode="json"),
            twosides_warfarin_aspirin.model_dump(mode="json"),
            label_fluox_tram.model_dump(mode="json"),
            faers_fluox_tram.model_dump(mode="json"),
            twosides_fluox_tram.model_dump(mode="json"),
            label_met_lis.model_dump(mode="json"),
            faers_met_lis.model_dump(mode="json"),
            twosides_met_lis.model_dump(mode="json"),
        ],
        "regimen_report": report.model_dump(mode="json"),
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"wrote {OUT} ({len(payload['source_findings'])} source findings + 1 report)")


if __name__ == "__main__":
    main()
