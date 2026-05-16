# Data sources — shapes, quirks, gotchas

Reference for backend developers. Real samples in `samples/`.

## RxNorm (rxnav.nlm.nih.gov)
**Auth:** none.
**Rate limit:** ~20 req/sec polite, no hard cap.

### `GET /REST/rxcui.json?name=<drugname>` → `samples/rxnorm_warfarin.json`
Returns RxCUI(s) matching a free-text name. Both ingredient names (warfarin → 11289) and brand names (Tylenol → 202433) resolve.

### `GET /REST/rxcui/<rxcui>/properties.json` → `samples/rxnorm_warfarin_properties.json`
Returns canonical name and TTY (term type). TTY of `IN` is the normalized ingredient.

### `GET /REST/rxcui/<rxcui>/related.json?tty=IN` → `samples/rxnorm_tylenol_to_ingredient.json`
Chains brand → ingredient. Required when input is a brand name (e.g. Tylenol 202433 → acetaminophen 161). Without this chain the synthesis agent will treat brand and generic names as different drugs.

**Gotcha:** `rxnormId` may be missing entirely for unknown drug names. Treat missing key as "no match".

## OpenFDA Label (api.fda.gov/drug/label)
**Auth:** none, but `OPENFDA_API_KEY` raises limit from 240 to 120k req/day.
**Rate limit:** 240/min unauth.

### `GET /drug/label.json?search=openfda.generic_name:<name>&limit=1` → `samples/openfda_label_warfarin.json`
Returns full prescribing label. Sections used by the source agent:
- `boxed_warning` — black-box warnings (highest severity signal)
- `drug_interactions` — narrative interaction text
- `drug_interactions_table` — HTML table, parse with `nano-30b` rather than regex
- `warnings_and_cautions` — broader risk text
- `contraindications` — absolute contraindications

**Gotcha:** The `warnings` key is **not** present on modern labels — it's been renamed `warnings_and_cautions`. Don't rely on the PRD's outdated field name.

**Gotcha:** Searching by RxCUI uses `search=openfda.rxcui:<rxcui>`. Many labels are missing `openfda.rxcui` — fall back to `openfda.generic_name` lookups.

## OpenFDA FAERS (api.fda.gov/drug/event)
**Auth:** none, same key/limit as Label.

### `GET /drug/event.json?search=patient.drug.openfda.generic_name:<a>+AND+patient.drug.openfda.generic_name:<b>&limit=N` → `samples/openfda_faers_warfarin_aspirin.json`
Returns adverse event case reports where **both** drugs are listed in the same patient. Each result is one case with:
- `patient.drug[]` — all drugs the patient was on
- `patient.reaction[].reactionmeddrapt` — MedDRA reaction terms

For source-agent purposes: paginate (or set `limit=100`), aggregate `reactionmeddrapt` counts across cases, return the top N reactions with frequencies.

**Gotcha:** Many cases have drugs listed only by `medicinalproduct` (brand) with `openfda.generic_name` missing. Pair queries by `openfda.generic_name` therefore undercount — acceptable for demo since major drugs are well-coded.

**Gotcha:** `+AND+` must be URL-encoded as plus signs (httpx may URL-encode the space; pass the full query string explicitly).

## PubChem (pubchem.ncbi.nlm.nih.gov)
**Auth:** none.

### `GET /rest/pug/compound/name/<drug>/property/CanonicalSMILES/JSON` → `samples/pubchem_warfarin_smiles.json`
**Gotcha:** PubChem renamed `CanonicalSMILES` to `ConnectivitySMILES` (the response key is `ConnectivitySMILES` even when you query `CanonicalSMILES`). Read whichever key is present.

PubChem is only needed if the third source (BE-03) requires SMILES. TWOSIDES queries by drug name, so PubChem may be cuttable — decide at BE-03.

## Demo regimen pre-validation
Each demo drug should be checked against all three free APIs before the build to ensure non-empty coverage. Add results to `docs/demo-cases.md` as JOINT-02 lands.
