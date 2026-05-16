# [PROJECT NAME] Task Breakdown

> **TODO(synthetic-data):** TWOSIDES leg is now backed by the real SNAP
> Decagon dataset (`data/decagon.sqlite`, built by `scripts/build_decagon.py`).
> The remaining hand-authored asset is `samples/fixtures.json` (frontend dev
> material) — regenerate from a live `/api/analyze` response before judging.
> `grep -rn "TODO(synthetic-data)" .` lists every remaining marker.

**Companion to PRD.md**
**Track:** Cloud (Brev + Nemotron) + NemoClaw
**Team:** 2 people (Person A = backend/agents, Person B = frontend/demo + design)
**Status:** Live, H0 now, 24h on the clock

## How to read this

Tasks are in priority order, grouped by build phase. Each task has:

- **ID** for reference
- **Owner:** Backend (BE), Frontend (FE), or Joint
- **Depends on:** which tasks must be complete first
- **Description:** what and why
- **Steps:** how to complete it
- **Acceptance:** how you know it's done
- **Time budget**

Backend and frontend tasks within the same phase usually parallelize. Watch dependency arrows for blockers.

Frontend tasks are open-ended on visual treatment. Oleg designs as he builds.

## Reality check

- No pre-hackathon time. Setup happens in H0-2 alongside foundation work.
- Keeping all three sources means the third source must be the fastest one to integrate (TWOSIDES SQLite probably wins, Decagon probably loses).
- Design happens in parallel with build, not before. Person B carries both jobs.
- Buffer is thin. The only real protection is H17-19. Defend it.

---

## Phase 0: Setup + foundation (H0 to H4)

This is the highest-risk phase. If access to Brev, Nemotron, or NemoClaw doesn't work, the whole project is blocked. Resolve all access issues in the first hour, period.

### [DONE] JOINT-00 · Access verification sprint
**Owner:** Joint
**Depends on:** nothing
**Time:** 45 min, hard cap

Get every dependency working before doing anything else. Whatever doesn't work in 45 minutes goes on a fallback list.

**Steps:**
1. Both teammates: confirm Brev login, credit balance
2. Launch a small Brev instance
3. Inference call against `nemotron-3-super-120b-a12b` (succeed or fail with error message)
4. Inference call against `nemotron-3-nano-30b-a3b`
5. Run `curl -fsSL https://nvidia.com/nemoclaw.sh | bash` on Brev instance
6. Test minimal NemoClaw policy enforcement (block all network, confirm it blocks)
7. Record all endpoint URLs in shared notes

**Acceptance:** Both Nemotron models respond. NemoClaw installs and enforces a basic policy. If anything fails, that becomes a fallback (e.g. OpenRouter instead of Brev for Nemotron, plain OpenClaw if NemoClaw is broken).

**If this takes more than 45 min, stop and reassess.** Time-boxing this is mandatory.

---

### [DONE] BE-01 · Repo scaffold + dependencies
**Owner:** Person A
**Depends on:** JOINT-00
**Time:** 30 min

**Steps:**
1. Create repo: `backend/`, `frontend/`, `samples/`, `policies/`, `docs/`
2. Backend: Python 3.11+, `pyproject.toml` with langgraph, openclaw, fastapi, httpx, pydantic
3. `.env.example` with Brev endpoint, model names, third-source config
4. FastAPI app with `/health` endpoint
5. Push to GitHub, both teammates clone

**Acceptance:** Both teammates have repo cloned, `pip install -e .` works, FastAPI runs locally.

---

### [DONE] BE-02 · Data source smoke tests
**Owner:** Person A
**Depends on:** BE-01
**Time:** 30 min

Hit every data source you plan to use. Save real samples for the team to reference.

**Steps:**
1. RxNorm `/REST/rxcui.json?name=warfarin`, save response
2. OpenFDA Label `/drug/label.json?search=...` for Warfarin, save response
3. OpenFDA FAERS `/drug/event.json?search=...` for Warfarin, save response
4. Save all samples to `samples/` with descriptive filenames
5. Document any non-obvious quirks in `docs/data-sources.md`

**Acceptance:** `samples/` has real JSON from each free API. Response shapes documented.

---

### [DONE] BE-03 · Third source decision + integration
**Owner:** Person A
**Depends on:** BE-02
**Time:** 1 hour, hard cap

Pick the third source NOW. Default to TWOSIDES because it's the fastest to integrate. Decagon and ChemBERTa take longer and have higher failure risk.

**Steps:**
1. Decide in 5 minutes: TWOSIDES SQLite is the default. Only deviate if there's a strong specific reason.
2. Download TWOSIDES CSV from Tatonetti Lab (or use a precomputed subset if main file is too large)
3. Load into SQLite locally on the Brev instance
4. Write `query_twosides(drug_a, drug_b) -> dict` function
5. Test against 3 demo drug pairs, confirm meaningful results

**Acceptance:** Given two drug names, function returns adverse event data with statistical confidence scores. Demo pairs pre-validated.

**If TWOSIDES isn't working in 1 hour, fall back to mocking the third source with a small hardcoded lookup table for the demo cases.** Don't burn 3 hours on data infrastructure.

---

### [DONE] JOINT-01 · Lock the JSON schema
**Owner:** Joint, critical coordination point
**Depends on:** BE-01, BE-02 (helpful, not blocking)
**Time:** 30 min, do this around H1

Define the contract between source agents and synthesis, and between backend and frontend.

**Steps:**
1. Both teammates at the same screen
2. Draft schema from PRD section 8
3. Validate it covers OpenFDA Label, FAERS, and TWOSIDES outputs
4. Encode as Pydantic models in `backend/schemas.py`
5. Generate 9 fixtures (3 sources × 3 example findings each) in `samples/fixtures.json`

**Acceptance:** `schemas.py` exists. `fixtures.json` exists with realistic data. Both teammates have agreed: schema changes after H5 require both to sign off.

---

### [IN PROGRESS] JOINT-02 · Demo cases + design direction
**Owner:** Joint (15 min for cases) + Person B (rest is design)
**Depends on:** BE-02
**Time:** 30 min joint, then Person B continues design work in parallel

**Steps (joint, 15 min):**
1. Pick primary regimen: 6 drugs a real patient might take, including at least one pair with cross-source disagreement potential. Warfarin + Aspirin should be in there as the known-major anchor case. Frame it as a patient's actual med list, not a clinical test case.
2. Pick follow-up case: primary + ibuprofen (something a patient might add OTC) for memory demo
3. Design attack case: input with embedded prompt injection or off-whitelist URL for NemoClaw block demo
4. Document in `docs/demo-cases.md`

**Steps (Person B continues alone, 1-2h):**
5. Sketch frontend layout direction — patient-first: warm, approachable, not clinical
6. Pick visual identity (typography, color, motion vocabulary, layout — avoid sterile hospital aesthetic)
7. Mock up the key states: input, fan-out, synthesis moment, plain-language patient report, NemoClaw block


---

### [DONE] BE-04 · RxNorm normalization tool
**Owner:** Person A
**Depends on:** JOINT-01, BE-02
**Time:** 45 min

Tool that takes free-text drug name, returns normalized identifier.

**Steps:**
1. Implement async `normalize_drug(name: str) -> NormalizedDrug`
2. Call RxNorm `/REST/rxcui.json` and `/REST/rxcui/<id>/properties.json`
3. Return RxCUI, generic name, brand names
4. Handle drug-not-found gracefully
5. Test against Warfarin, Aspirin, Tylenol, and brand names

**Acceptance:** `normalize_drug("Tylenol")` returns normalized acetaminophen. Edge cases don't crash.

---

### [DONE] FE-01 · Frontend scaffold + design implementation start
**Owner:** Person B
**Depends on:** JOINT-01
**Time:** 1.5h

Set up the frontend project and start implementing the design from JOINT-02.

**Steps (open-ended on visual treatment):**
1. Vite + React in `frontend/`
2. Styling approach decided based on design (CSS modules, vanilla CSS, or CSS-in-JS, NO Tailwind)
3. Set up environment config for backend URL
4. Implement the basic layout shell from design mockups
5. Load fixtures from `samples/fixtures.json`
6. Mock API module that returns fixtures, with env toggle to real backend later

**Acceptance:** Dev server runs. Layout shell renders. Fixtures load and are displayed in basic form. Design direction visible.

---

## Phase 1: Source agents (H4 to H7)

### [DONE] BE-05 · OpenFDA Label source agent
**Owner:** Person A
**Depends on:** JOINT-01, BE-04
**Time:** 1.5h

**Steps:**
1. Implement async `query_openfda_label(drug_a, drug_b) -> SourceFindings`
2. Query `/drug/label.json` with `search=openfda.rxcui:<rxcui>` for each drug
3. Extract `drug_interactions`, `contraindications`, `warnings`, `boxed_warning`
4. Use nano-30b to check if drug B mentioned in drug A's label as interaction (and vice versa)
5. Return SourceFindings in locked schema
6. Handle empty results, missing fields, rate limits

**Acceptance:** (Warfarin, Aspirin) returns SourceFindings with at least one interaction. (Warfarin, unrelated drug) returns `coverage: no_data` or empty findings without crashing.

---

### [DONE] BE-06 · OpenFDA FAERS source agent
**Owner:** Person A
**Depends on:** BE-05
**Time:** 1.5h

**Steps:**
1. Implement `query_faers(drug_a, drug_b) -> SourceFindings`
2. Query `/drug/event.json` with both drugs as filter
3. Aggregate co-reported reactions (count by `reactionmeddrapt`)
4. Filter to reactions with frequency above threshold (5-10)
5. Use nano-30b to summarize top reactions into schema fields
6. Return findings with frequency in evidence section

**Acceptance:** (Warfarin, Aspirin) returns FAERS findings showing bleeding-related events with frequencies. Sparse cases handled.

---

### [DONE] BE-07 · TWOSIDES source agent
**Owner:** Person A
**Depends on:** BE-03
**Time:** 45 min

Wrap the TWOSIDES query function as a source agent matching the schema.

**Steps:**
1. Implement `query_twosides(drug_a, drug_b) -> SourceFindings`
2. Call the query function from BE-03
3. Map TWOSIDES output (side effects with statistical significance) into shared schema
4. Set `severity_hint` from significance score, `coverage`, `confidence`
5. Handle drug coverage gaps with `coverage: no_data`

**Acceptance:** Returns SourceFindings for demo pairs. Drug coverage gaps explicit.

---

### FE-02 · Agent graph + report scaffolds
**Owner:** Person B
**Depends on:** FE-01
**Time:** 3h

Build the two big visual components in parallel: the agent graph and the report panel.

**Steps (open-ended on visual treatment):**
1. Agent graph component with 5 nodes (Intake, OpenFDA Label, FAERS, TWOSIDES, Synthesis)
2. Each node has states: idle, querying, complete, error
3. Hook up to mock data with setTimeouts simulating real fan-out timing
4. Synthesis transition designed as visual peak (per design)
5. Report panel scaffolded with fixture data
6. Severity visualization (per design)
7. Expandable evidence sections
8. Clinician/patient view toggle structure (content can come later)

**Acceptance:** Agent graph cycles through all states. Report panel renders ranked interactions from fixtures with evidence and severity visible.

---

## Phase 2: Synthesis (H7 to H13)

This is the intellectual core. 6 hours is the right budget. Do not cut this.

### [DONE] BE-08 · Synthesis agent v1
**Owner:** Person A
**Depends on:** BE-05, BE-06, BE-07
**Time:** 2h

Get a basic working synthesis. Polish later.

**Steps:**
1. Write synthesis prompt with severity rubric inline (major / moderate / minor / contraindicated / no_concern with clear criteria)
2. Pass list of SourceFindings for single drug pair
3. Have it return structured JSON with severity, reasoning, citations
4. Define and validate `SynthesizedInteraction` Pydantic model
5. Test against (Warfarin, Aspirin) manually
6. Confirm super-120b is actually being used

**Acceptance:** Given source findings for (Warfarin, Aspirin), returns SynthesizedInteraction with severity "major" and reasoning referencing 2+ sources. Output passes Pydantic validation.

---

### [IN PROGRESS] BE-09 · Synthesis prompt iteration
**Owner:** Person A
**Depends on:** BE-08
**Time:** 3h

The most important block of time in the whole build. Iterate the prompt against adversarial cases.

**Test cases:**
- Warfarin + Aspirin: clear major (calibration baseline)
- Fluoxetine + Tramadol: serotonin syndrome (subtle reasoning)
- Metformin + Lisinopril: real but moderate (calibration check, do you over-call?)
- A pair with deliberate source disagreement (find one in your data, this is the hardest test)

**Steps:**
1. Run synthesis on each case, manually evaluate
2. Iterate prompt: severity rubric specifics, chain-of-thought structure, disagreement-handling instructions, mandatory citations
3. Watch for: false confidence on uncertain cases, hallucinated citations, miscalibrated severity, silently picking winners on disagreement
4. Commit final prompt to `prompts/synthesis.md`

**Acceptance:** All 4 cases produce outputs passing human review. Correct severity, faithful citations, explicit disagreement reasoning where present.

**If you're behind at H10, this is what you protect.** Cut polish, cut the patient view, cut the bells. Keep iterating synthesis.

---

### [DONE] BE-10 · Report assembly
**Owner:** Person A
**Depends on:** BE-09
**Time:** 45 min

Aggregate per-pair syntheses into a full regimen report. Patient plain-language output is the primary view.

**Steps:**
1. Take list of SynthesizedInteraction
2. Sort by severity
3. Produce `RegimenReport` with overall summary, ranked pairs, source attribution
4. Generate plain-language patient version using nano-30b: what this means for you, what symptoms to watch for, what to ask your doctor
5. Detailed view (severity scores, citations) is secondary — same data, different rendering

**Acceptance:** Given syntheses for all 15 pairs of 6-drug regimen, returns RegimenReport sorted by severity. Patient view is plain English with "what to ask your doctor" prompts. Detailed view has citations and severity labels.

---

### FE-03 · Synthesis moment + report content
**Owner:** Person B
**Depends on:** FE-02
**Time:** 2.5h

Iterate on the report panel with richer fixture data. Design and build the synthesis transition.

**Steps (open-ended on visual treatment):**
1. Design and build the moment Nemotron is "thinking" - this is the demo peak
2. Make the cross-source reasoning visible (not just final answer)
3. Iterate on report panel: plain-language patient view is the default — severity expressed in human terms ("serious risk", "watch out for"), expandable for evidence and citations
4. Toggle to detailed view showing technical severity labels and source citations
5. "What to ask your doctor" prompts rendered per flagged pair
6. Add memory state indicator placeholder (lights up on follow-up)
7. Add empty/error states

**Acceptance:** Synthesis moment is theatrical and demoable. Report panel defaults to plain-language patient view and feels finished against fixtures. Detailed view toggle works.

---

### FE-04 · Demo script first draft
**Owner:** Person B
**Depends on:** FE-03, JOINT-02
**Time:** 30 min

Write the demo script as words on a page. Narrate from the patient's perspective, not a clinician's.

**Steps:**
1. Write 3-minute demo flow per PRD section 15 — open with the patient story, not the technical architecture
2. Time it (read aloud)
3. Identify dead-air moments, plan what to say
4. Mark visual peaks
5. Confirm both teammates know their lines

**Acceptance:** Written script. Runs 2:45-3:15 read aloud at normal pace. Patient framing holds throughout.

---

## Phase 3: Integration (H13 to H14)

### [DONE] BE-11 · LangGraph orchestration + intake
**Owner:** Person A
**Depends on:** BE-04, BE-05, BE-06, BE-07, BE-10
**Time:** 1.5h

Full LangGraph pipeline: intake → parallel fan-out → synthesis → report.

**Steps:**
1. Define LangGraph state object: regimen, pair list, source findings, syntheses, final report
2. Intake node: normalize drugs, generate pairs, populate state
3. Parallel fan-out using LangGraph's parallel execution (one branch per source × pair)
4. Synthesis node firing once all source branches complete
5. Report assembly node
6. Wire `/api/analyze` FastAPI endpoint running the graph end-to-end

**Acceptance:** Hitting `/api/analyze` with regimen returns full RegimenReport. Logs show parallel execution. Pipeline runs under 30s for 6-drug regimen.

---

### [DONE] BE-12 · Memory layer
**Owner:** Person A
**Depends on:** BE-11
**Time:** 45 min

Persist regimen and findings across queries so follow-ups only re-evaluate delta.

**Steps:**
1. Simple in-process session cache (don't over-engineer, OpenClaw memory if it's easy, otherwise dict)
2. Key by session ID
3. On query, check memory: if regimen overlaps, only fan out for new pairs
4. Update memory with new findings
5. Return report including both cached and new pairs, marked

**Acceptance:** 6-drug regimen → 15 pairs evaluated. Follow-up "add ibuprofen" → only 6 new pairs evaluated. Report shows delta clearly.

---

## Phase 4: NemoClaw (H14 to H17)

### [DONE] BE-13 · NemoClaw policy authoring
**Owner:** Person A
**Depends on:** BE-11, JOINT-00
**Time:** 45 min

Write the production NemoClaw policy.

**Steps:**
1. Network whitelist: api.fda.gov, rxnav.nlm.nih.gov, Nemotron endpoint, anything else needed
2. Filesystem policy: write to `/session/*` only, deny rest
3. Disable subprocess spawning
4. Enable audit logging to `/session/audit.log`
5. Save as `policies/policy.yaml`

**Acceptance:** Policy file written. Network whitelist matches actually-used endpoints.

---

### [DONE] BE-14 · NemoClaw deployment + verification
**Owner:** Person A
**Depends on:** BE-13
**Time:** 1.5h

Run the actual agent under NemoClaw.

**Steps:**
1. Launch agent through NemoClaw with `policies/policy.yaml`
2. Run real regimen query end-to-end, confirm still works
3. Check audit log contents
4. Run attack case from JOINT-02, confirm OpenShell blocks
5. Save audit log excerpt for demo

**Acceptance:** Agent runs successfully under NemoClaw. Attack case blocked with block visible in audit log. Audit excerpt saved.

**If NemoClaw is broken at H16, cut losses and document the attempt.** Cloud track still ships.

---

### [DONE] BE-15 · NemoClaw demo endpoints
**Owner:** Person A
**Depends on:** BE-14
**Time:** 30 min

Surface NemoClaw state to frontend.

**Steps:**
1. `/api/audit-log` returns recent OpenShell entries
2. `/api/policy` returns YAML policy as text
3. Frontend can trigger attack case (special demo flag or button)
4. Block surfaces in API responses

**Acceptance:** Frontend can fetch policy, audit log, and trigger attack case.

---

### FE-05 · Wire real backend
**Owner:** Person B
**Depends on:** BE-11, FE-03
**Time:** 1h

Replace mock API with real backend calls.

**Steps:**
1. Update API module to hit real backend
2. Handle real latency states (agent graph reflects actual completion times)
3. Handle real error states
4. Memory state indicator lights up on follow-ups
5. Confirm all demo cases work against real backend

**Acceptance:** Demo cases run end-to-end against real backend. Agent graph reflects real timing. Memory indicator works.

---

### FE-06 · NemoClaw enforcement view
**Owner:** Person B
**Depends on:** FE-05, BE-15
**Time:** 1.5h

Build the NemoClaw demo moment.

**Steps (open-ended on visual treatment):**
1. Build per design from JOINT-02
2. Show YAML policy (or relevant excerpt) at moment of block
3. Render attack-case denial visually
4. Show audit log entry of blocked call
5. Make it land theatrically

**Acceptance:** Triggering attack case produces clear visual moment showing block, policy, audit log entry. Demoable to judges.

---

## Phase 5: Buffer (H17 to H19)

### JOINT-03 · Full demo run-through
**Owner:** Joint
**Depends on:** FE-05, FE-06, BE-15
**Time:** 30 min

Run full demo as if for a judge. Note everything broken.

**Acceptance:** Prioritized fix list exists.

---

### JOINT-04 · Fix top 3 issues
**Owner:** Joint
**Depends on:** JOINT-03
**Time:** 1.5h

Fix the top 3 from JOINT-03. Resist fixing everything.

**Acceptance:** Top 3 fixed. Demo runs through cleanly enough to record.

---

## Phase 6: Polish + rehearsal (H19 to H23)

### FE-07 · Backup demo video
**Owner:** Person B
**Depends on:** JOINT-04
**Time:** 1h

Insurance policy.

**Steps:**
1. Screen-record full successful demo run
2. Record voice-over
3. Light editing if needed
4. Upload (YouTube unlisted, Loom)
5. Link in README

**Acceptance:** Backup video exists showing full successful demo.

---

### JOINT-05 · Demo rehearsal x3
**Owner:** Joint
**Depends on:** JOINT-04, FE-07
**Time:** 1h

Run the demo three times. Refine the script.

**Steps:**
1. Run 1: identify rough spots
2. Run 2: tighten script
3. Run 3: lock script
4. Practice judge Q&A out loud, especially "why NemoClaw" and "why Nemotron"

**Acceptance:** All runs under 3:15. Lines known. Q&A practiced.

---

### [DONE] BE-16 · README (Cloud track)
**Owner:** Person A
**Depends on:** JOINT-04
**Time:** 45 min

**Steps:**
1. Project description, one paragraph
2. Architecture diagram from PRD
3. How to run locally (env, Brev, install)
4. Data sources with attribution
5. Team info
6. Backup video link
7. Known limitations + production roadmap

**Acceptance:** README at repo root renders cleanly on GitHub.

---

### [DONE] BE-17 · README (NemoClaw track)
**Owner:** Person A
**Depends on:** BE-16
**Time:** 30 min

**Steps:**
1. Why NemoClaw for this use case (PHI + prompt injection story)
2. YAML policy walkthrough
3. Sample audit log excerpts
4. Attack case explanation
5. Production deployment notes

**Acceptance:** `README-NEMOCLAW.md` exists.

---

## Phase 6 · Agent Skills

### [DONE] BE-16 · Schema — DeepResearchReport
**Owner:** Backend
**Depends on:** JOINT-01
**Description:** Append `DeepResearchFinding` and `DeepResearchReport` to `backend/schemas.py` without touching `RegimenReport`.
**Acceptance:** `from backend.schemas import DeepResearchReport` works; existing `RegimenReport` unchanged.

---

### [DONE] BE-17 · Policy — add brave/telegram/vercel hosts
**Owner:** Backend
**Depends on:** BE-15
**Description:** Add `api.search.brave.com`, `api.telegram.org`, and vercel placeholder to `policies/policy.yaml`.
**Acceptance:** Policy YAML parses; new host entries present.

---

### [DONE] BE-18 · Skill — Analyze
**Owner:** Backend
**Description:** `skills/analyze/SKILL.md` + `scripts/analyze.py`. POSTs to `ACUITY_API_BASE_URL/api/analyze`, prints `RegimenReport` JSON to stdout.
**Acceptance:** `python skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin"]'` returns valid JSON with `schema_version: "1.0"`.

---

### [DONE] BE-19 · Skill — MakeReport
**Owner:** Backend
**Depends on:** BE-16
**Description:** `skills/make_report/` with `make_report.py` (entrypoint), `render_regimen.py`, `render_deep_research.py`, `template.py`. Auto-detects schema, generates PDF via ReportLab.
**Acceptance:** Both `RegimenReport` and `DeepResearchReport` inputs produce readable PDFs.

---

### [DONE] BE-20 · Skill — Reminder
**Owner:** Backend
**Description:** `skills/reminder/` with `create.py`, `list.py`, `cancel.py`, `send.py`. NemoClaw-isolated: crontab + `/session/reminders/` + Telegram.
**Acceptance:** `create.py` writes JSON and crontab line; `send.py` posts to Telegram; `cancel.py` removes both.

---

### [DONE] BE-21 · Skill — DeepResearch
**Owner:** Backend
**Depends on:** BE-16, BE-17
**Description:** `skills/deep_research/` with `deep_research.py`, `brave_search.py`, `synthesize.py`. Fans out 6 Brave queries per drug, synthesizes with Nemotron.
**Acceptance:** `python skills/deep_research/scripts/deep_research.py --drug "metformin"` returns `DeepResearchReport` with ≥4 findings.

---

### [DONE] BE-22 · Skill — DB stubs
**Owner:** Backend
**Description:** `skills/db/` with `db_read.py` and `db_write.py` as TODO stubs. Exit 2 with JSON status message.
**Acceptance:** Both scripts exit 2 with parseable JSON on stderr.

---

### [DONE] BE-23 · Skills test plan
**Owner:** Backend
**Description:** `docs/skills-test-plan.md` with agent prompts, expected behavior, and verification steps for all 5 skills.
**Acceptance:** Document covers Analyze, MakeReport (both schemas), DeepResearch, Reminder (create/list/cancel), DB stubs, policy gate, and end-to-end pipeline.

---

## Phase 7: Submit (H23 to H24)

### JOINT-06 · Final submit
**Owner:** Joint
**Depends on:** all prior
**Time:** 30 min

**Steps:**
1. Final commit and push
2. Submit Cloud track (form, repo, video)
3. Submit NemoClaw track (form, repo, video, policy file)
4. Confirm both accepted
5. Sleep

**Acceptance:** Both submissions confirmed.

---

## Critical path

Backend is the critical path. Frontend parallelizes after JOINT-01.

```
JOINT-00 → BE-01 → BE-02 → BE-03 → JOINT-01 → BE-04 → BE-05, BE-06, BE-07 → BE-08 → BE-09 → BE-10 → BE-11 → BE-12 → BE-13 → BE-14 → BE-15
                                ↓
                            JOINT-02 (design direction starts)
                                ↓
                            FE-01 → FE-02 → FE-03 → FE-04 → FE-05 → FE-06 → FE-07
```

## Time budget

| Phase | Hours | Cumulative |
|-------|------:|-----------:|
| 0: Setup + foundation | 4 | 4 |
| 1: Source agents | 3 | 7 |
| 2: Synthesis | 6 | 13 |
| 3: Integration | 1 | 14 |
| 4: NemoClaw | 3 | 17 |
| 5: Buffer | 2 | 19 |
| 6: Polish + rehearsal | 4 | 23 |
| 7: Submit | 1 | 24 |

## What to cut if you're behind

In this order:

1. **Detailed/technical view of report** (nice but not required for demo — patient view ships first)
2. **TWOSIDES integration** (fall back to hardcoded lookup for demo cases)
3. **Memory layer polish** (basic cache is fine, don't use OpenClaw memory if it's flaky)
4. **NemoClaw integration** (Cloud track still ships, lose bonus track only)
5. **Frontend polish beyond MVP** (agent graph + report panel + NemoClaw moment is the minimum)

What you do NOT cut:
- Synthesis prompt iteration (BE-09). Protect this.
- The schema lock (JOINT-01). Don't proceed without it.
- The demo rehearsals (JOINT-05). Practiced demos beat polished ones.

## Hour-zero checklist

Before you do anything else:
- [ ] Both teammates have Brev access working
- [ ] Both Nemotron models respond to inference calls
- [ ] NemoClaw installs and enforces a basic policy
- [ ] Repo created, both teammates pushing
- [ ] PRD and TASKS docs open in shared tab
- [ ] Snacks within arm's reach

Start the clock. Good luck.
