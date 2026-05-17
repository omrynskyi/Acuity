from __future__ import annotations

from backend.graph import intake_node
from backend.schemas import NormalizedDrug


async def test_intake_node_filters_target_drug_by_normalized_alias(monkeypatch) -> None:
    async def fake_normalize_regimen(_raw: list[str]) -> list[NormalizedDrug]:
        return [
            NormalizedDrug(
                input_name="Tylenol",
                rxcui="161",
                generic_name="acetaminophen",
                brand_names=["Tylenol"],
                found=True,
            ),
            NormalizedDrug(
                input_name="Terazosin",
                rxcui="37798",
                generic_name="terazosin",
                brand_names=[],
                found=True,
            ),
            NormalizedDrug(
                input_name="Advil",
                rxcui="5640",
                generic_name="ibuprofen",
                brand_names=["Advil"],
                found=True,
            ),
        ]

    monkeypatch.setattr("backend.graph.normalize_regimen", fake_normalize_regimen)

    state = await intake_node(
        {
            "session_id": "demo",
            "raw_regimen": ["Tylenol", "Terazosin", "Advil"],
            "target_drug": "tylenol",
            "durations_ms": {},
        }
    )

    assert state["pairs"] == [
        ("acetaminophen", "ibuprofen"),
        ("acetaminophen", "terazosin"),
    ]
