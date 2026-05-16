
# ACUITY PRD

**Status:** Draft v0.1
**Authors:** Oleg + teammate
**Hackathon:** NVIDIA / ASUS / Baskin 24h
**Target tracks:** Cloud (Brev + Nemotron) AND NemoClaw bonus, both primary
**Build window:** 24 hours

---

## 1. What we're building

An autonomous multi-agent system that takes a patient's own medication list, queries multiple heterogeneous data sources in parallel, reconciles conflicting findings with Nemotron, and returns a plain-language risk report that helps the patient understand their drug interactions and know what to ask their doctor.

The product runs as an OpenClaw multi-agent system orchestrated with LangGraph (or equivalent), powered by Nemotron models (`nemotron-3-super-120b-a12b` for synthesis reasoning, `nemotron-3-nano-30b-a3b` for source agents if latency matters), deployed on Brev. The same agent system is wrapped in NemoClaw via OpenShell policies for the bonus track, demonstrating PHI containment and API whitelist enforcement.

## 2. Why this matters

Polypharmacy (5+ concurrent meds) affects ~40% of adults 65+. A 10-drug regimen has 45 unique drug pairs that need to be checked. Patients are sent home with complex medication regimens and no practical way to understand what they're taking together. Preventable medication errors are linked to ~125K deaths per year in the US — and most patients never know there was a risk.

Patients can't manually reconcile drug interactions across regulatory labels, adverse event databases, and research datasets. Even if they Google each pair, they get clinical jargon, conflicting results, and no synthesis.

A multi-agent system can give every patient the same quality of analysis a pharmacist would apply — in plain language, in seconds.

## 3. Goals and non-goals

### Goals
- Working deployed agent on Brev with live demo capability
- Parallel fan-out across 3+ heterogeneous data sources
- Nemotron-powered synthesis that explicitly reasons about source disagreement
- Persistent memory across queries (regimen tracking)
- Plain-language patient report as the primary output, severity-ranked with source citations
- NemoClaw-wrapped deployment demonstrating at least one privacy or security control

### Non-goals
- Production clinical validation
- EHR / FHIR integration (architecture supports it, not built)
- Custom ML model training from scratch
- Replacing medical advice or prescribing decisions (this is a research prototype, demo only)
- Coverage of every drug in existence (demo cases curated for source coverage)
- Clinician-facing workflow tools (out of scope for this demo)

## 4. Success criteria

The submission ships if all of these are true at hour 24.

- Live demo runs end to end on a real polypharmacy case in under 30 seconds
- All 3 source agents return real data (not mocks) for the demo cases
- Synthesis agent produces a severity-ranked report with at least one moment of cross-source reasoning (e.g. source A says X, source B says Y, here's the reconciliation)
- Memory demo works (add a drug, only new pairs re-evaluated)
- NemoClaw wrapper deployed and demonstrating at least one privacy/security control
- README, demo video, and submission form complete for both tracks

Stretch:
- Demo handles a deliberately adversarial drug combination (uncommon interaction, sparse coverage)
- Side-by-side comparison of unguarded vs NemoClaw-guarded execution in the demo

## 5. Users and use cases

Primary user for the demo narrative: a patient managing multiple medications who wants to understand what they're taking together before their next doctor's appointment. They are not a clinician. They need plain-language explanations of which drug pairs carry risk, how serious those risks are, and what questions to bring to their doctor.

Demo flow they care about:
1. Enter their medication list (names they actually know — brand or generic)
2. See the system working on their behalf, pulling from multiple sources
3. Get a ranked, plain-language report: what's risky, how risky, and why
4. Add a new prescription, see only the new pairs re-evaluated

We are not building for: real-time prescribing, EHR integration, or research data mining (all out of scope).

## 6. Architecture overview

```
USER INPUT  →  medication list (name, dose, frequency)

INTAKE AGENT  (orchestrator)
  ├── normalize drug names via RxNorm
  ├── retrieve SMILES via PubChem (for any ML-based agent)
  ├── generate pairwise combinations
  └── fan out to parallel source agents

PARALLEL QUERY LAYER  (concurrent tool use)
  ├── OpenFDA Label Agent     → regulatory warnings
  ├── OpenFDA FAERS Agent     → empirical adverse event signals
  └── [ML / Curated Source]   → TBD (Decagon, ChemBERTa, TWOSIDES, etc.)

SYNTHESIS AGENT  (Nemotron)
  ├── aggregate normalized findings from all sources
  ├── reason about source agreement and disagreement
  ├── score severity on fixed rubric
  └── produce ranked report with citations

OUTPUT AGENT
  ├── patient view (plain language, primary — what this means for you, what to ask your doctor)
  └── detailed view (technical severity scores and source citations, secondary)

MEMORY LAYER
  └── regimen persistence across queries (OpenClaw memory)
```

### Why this shape

Three sources, not five. Each source captures a different epistemic type of evidence. The synthesis step is where the intelligence lives, not in any individual source.

The fan-out is parallel because the sources are independent. The synthesis is sequential because it depends on all sources completing. This is a canonical multi-agent orchestration pattern, well-suited to LangGraph (which the Nemotron track tutorials use).

### Framework and models
- **Orchestration:** OpenClaw with LangGraph for the agent graph. Parallel source nodes converge on the synthesis node. This is the canonical Nemotron-track pattern (used in the Report Generator tutorial) and maps cleanly to our fan-out-then-converge shape.
- **Synthesis agent:** `nvidia/nemotron-3-super-120b-a12b`. The reasoning trace is what carries the cross-source reconciliation, and the larger model earns its cost on this step.
- **Source agents:** `nvidia/nemotron-3-nano-30b-a3b`. These agents do less reasoning, mostly tool-call orchestration and result normalization into the shared schema. Smaller model keeps fan-out latency low.
- **Runtime:** NemoClaw (OpenClaw + OpenShell) for the secured deployment, plain OpenClaw on Brev as a fallback if NemoClaw integration breaks.

Memory persists the regimen so follow-up queries (adding a drug, removing a drug) only re-evaluate the delta, not the full pairwise matrix.

## 7. Data sources

### Confirmed
- **RxNorm** (NLM, free, no auth) for drug name normalization. Live API.
- **PubChem** (NIH, free, no auth) for SMILES retrieval. Live API.
- **OpenFDA Label** (api.fda.gov/drug/label) for regulatory interaction warnings. Live API, 240 req/min unauth.
- **OpenFDA FAERS** (api.fda.gov/drug/event) for adverse event reports. Live API, same rate limits.

### Third source (decision pending)
The third source covers the curated / ML-predictive signal. Options under consideration:
- Decagon precomputed predictions (graph-based, 2018, dated but established)
- ChemBERTa structural similarity (modern, lightweight, runs locally)
- TWOSIDES SQLite (curated polypharmacy dataset from Tatonetti Lab, static, free)
- Some combination

Decision deadline: end of pre-hackathon setup. Architecture is source-agnostic from the synthesis agent's perspective as long as the source returns the shared JSON schema.

## 8. Tool / agent contracts

All source agents return a common JSON schema. This is the single most important interface in the system.

```json
{
  "source": "openfda_label" | "openfda_faers" | "<third_source>",
  "drug_pair": ["drug_a_normalized", "drug_b_normalized"],
  "queried_at": "ISO8601",
  "findings": [
    {
      "type": "interaction" | "adverse_event" | "predicted_effect",
      "description": "free text from the source",
      "severity_hint": "major" | "moderate" | "minor" | null,
      "evidence": {
        "raw_excerpt": "string",
        "frequency": "number | null",
        "probability": "number | null",
        "source_url": "string | null"
      }
    }
  ],
  "coverage": "full" | "partial" | "no_data",
  "confidence": "high" | "medium" | "low"
}
```

Notes on the schema:
- `severity_hint` is what the source itself says, not the final synthesized severity
- `coverage: "no_data"` is meaningful, the synthesis agent needs to know when a source had nothing
- `evidence` fields are optional, source-dependent
- All severity vocabulary is fixed (major / moderate / minor) so synthesis can compare across sources

The synthesis agent receives a list of these objects and produces a single output report.

## 9. Synthesis agent (Nemotron)

This is the centerpiece. Most engineering time goes here.

### Inputs
- Patient regimen (list of normalized drug names)
- List of source findings (using the schema above), one per drug pair per source

### Outputs
A structured report with:
- Per-pair severity score (major / moderate / minor / contraindicated / no_concern)
- Plain-language explanation of each risk (primary output, written for a patient)
- Reasoning trace explaining why each pair received its score (shown in detailed view)
- Explicit notes when sources disagree
- Citations pointing to specific findings from specific sources
- "What to ask your doctor" prompts for flagged pairs
- A "predicted but unverified" flag for findings supported by some sources but not others

### Prompt design principles
- Severity rubric is in the system prompt, not assumed
- The model must reason out loud about source disagreement, not silently pick a winner
- Citations are mandatory (no claim without a source pointer)
- Output is JSON, validated before rendering

### Test cases for prompt iteration
- **Warfarin + Aspirin** (well-known major bleeding interaction, easy win, all sources should agree)
- **Fluoxetine + Tramadol** (serotonin syndrome risk, more subtle, tests reasoning depth)
- **Metformin + Lisinopril** (commonly co-prescribed, real but modest interaction risk, tests calibration)
- **A pair with deliberate source disagreement** (chosen after testing, demonstrates reconciliation)

If the synthesis agent confidently calls a real major interaction "minor" or invents a citation, the prompt is broken. Fix before moving on from hour 14.

## 10. Memory layer

OpenClaw persistent memory holds the patient context across queries. Specifically:

- The patient's current regimen (list of drugs)
- The full pairwise interaction matrix from the last query
- Synthesis outputs keyed by pair

When a follow-up query arrives ("add ibuprofen"), the agent:
1. Identifies the delta (new pairs only)
2. Queries sources only for the new pairs
3. Updates the matrix
4. Re-renders the report

This is one specific demonstrable capability, not "general persistent context."

## 11. Frontend

React, no Tailwind. Styling approach TBD (CSS modules, vanilla CSS, or a small CSS-in-JS like vanilla-extract or stitches, deciding before H1).

### Design status
Design not yet done. Needs a separate pass before hackathon, ideally a rough mockup or wireframe locked at H0 so frontend work isn't blocked on design decisions during the build.

### What the frontend needs to do
- Take a regimen as input (accept brand names and generics — patients don't know the difference)
- Show live agent activity during fan-out (which agents are running, completed, errored)
- Highlight the synthesis step as a distinct moment (the demo's intellectual peak)
- Display the synthesized report in plain language as the default view, severity-ranked with expandable evidence and "what to ask your doctor" prompts
- Toggle to a detailed view showing source citations and technical severity scores
- Show memory state on follow-up queries (which pairs are new, which are cached)
- For the NemoClaw track demo, show evidence of the policy/privacy control in action

### Design constraints
- Demo-driven, not user-driven. The frontend exists to make the agent's work visible during a 3-minute pitch, not to be a clinical product.
- Distinguishable on a projector from across a room. Color and motion carry meaning at distance.
- The synthesis moment is the visual peak. Whatever else gets cut, the synthesis reveal must land.
- Function over polish, but distinct from generic "AI dashboard" aesthetic. Judges will see many React+Tailwind dashboards today.

### Open design questions (for the separate design pass)
- Visual metaphor for the agent graph (node-and-edge graph? Spatial layout? Timeline?)
- How to communicate severity (color is obvious but limited, what else?)
- How to make source disagreement visually legible
- How to show the memory delta on follow-up queries
- Typography and identity (the brief is patient-empowerment, not clinical — warm and approachable, not sterile hospital aesthetic)
- NemoClaw control demonstration (how does "PHI redacted" or "tool restricted" look on screen?)

Scope discipline: function over polish during the build itself. Three hours max on frontend implementation after the agent graph is working. The design pass before the hackathon is what makes those three hours productive.

## 12. NemoClaw track

NemoClaw is OpenClaw plus OpenShell, a secure runtime enforcing YAML policies over file, network, and system resources. The core agent code is unchanged. Integration is primarily about authoring the right policy and demonstrating it.

### Why NemoClaw for this project (the answer judges want)
Polypharmacy reconciliation operates on protected health information. The medication regimen, even without a name attached, is sensitive. NemoClaw lets us deploy the agent with:
- **API whitelist:** the agent can reach exactly four hosts (api.fda.gov, rxnav.nlm.nih.gov, pubchem.ncbi.nlm.nih.gov, and the Nemotron inference endpoint). Any other outbound call is blocked.
- **Filesystem containment:** the agent can write to a designated session directory only, not to the host filesystem.
- **No shell execution:** the agent cannot spawn subprocesses, preventing prompt-injection-driven command execution.
- **Audit logging:** every tool call and file access is logged via OpenShell for review.

This is a defensible answer to "why NemoClaw not plain OpenClaw." The same architecture without NemoClaw could exfiltrate patient data via a prompt injection in a drug label or FAERS event description. With NemoClaw, that attack surface is closed at the runtime level.

### What the demo shows
Two policy enforcement moments in the live demo:
1. **API whitelist in action:** show the agent successfully calling api.fda.gov, then attempt (via a deliberately crafted test input) to make it reach an off-whitelist domain. OpenShell blocks it. Log displayed.
2. **Audit trail:** show the OpenShell log of all tool calls during a real query, demonstrating that every action is recorded.

### YAML policy structure (draft)
```yaml
# nemoclaw-policy.yaml (placeholder, refined during build)
network:
  allow:
    - api.fda.gov
    - rxnav.nlm.nih.gov
    - pubchem.ncbi.nlm.nih.gov
    - <nemotron-inference-endpoint>
  deny: "*"
filesystem:
  allow_write: ["/session/*"]
  deny: "*"
process:
  allow_spawn: false
audit:
  log_all_tool_calls: true
  log_destination: "/session/audit.log"
```

### Pre-hackathon work
- Run `curl -fsSL https://nvidia.com/nemoclaw.sh | bash` and confirm it works
- Read OpenShell policy documentation, understand YAML schema
- Decide between local install and Brev Launchable with `nvidia/nemotron-3-super-120b-a12b`
- Identify which policy controls are demoable in the current preview

### Risk
Preview-stage tooling. Documentation may be sparse. Mitigation: keep Cloud track functionally independent of NemoClaw. If NemoClaw integration breaks, the Cloud track still ships.

## 13. Build plan (24h)

### Pre-hackathon
- Get OpenClaw running locally (both teammates)
- Provision Brev instance, confirm Nemotron access
- Hit OpenFDA Label, FAERS, RxNorm, PubChem once each, confirm response shapes
- Decide and test the third source (download data, install model, whichever)
- Identify and pre-validate 3 demo drug combinations against all three sources

### Hour-by-hour
- **H0-1:** Joint setup. Lock the JSON schema. Person B starts on fixtures. Confirm NemoClaw access works.
- **H1-4:** Person A on RxNorm + OpenFDA Label tools. Person B on frontend scaffold (no Tailwind, see section 11).
- **H4-7:** Person A on FAERS + third source tools. Person B on agent graph component.
- **H7-13:** Person A on synthesis prompt iteration against 3 test cases. Person B on report panel and demo script.
- **H13-14:** Person A on intake agent + parallel fan-out + memory. Cloud track agent functionally complete.
- **H14-17:** Person A on NemoClaw integration. Person B wires real backend into frontend, swaps fixtures.
- **H17-19:** Joint buffer. Whatever broke under live conditions gets fixed. Memory demo validated.
- **H19-21:** Polish. Person B records backup demo video for both tracks.
- **H21-23:** Joint rehearsal x3, time the demo, prepare judge Q&A.
- **H23-24:** READMEs for both tracks, submit, sleep optional.

## 14. Role split

**Person A (backend / agents lead):** OpenClaw scaffold, all tool wrappers, synthesis prompt, memory, FastAPI surface. Owns the critical path.

**Person B (frontend / demo lead):** React UI, agent graph, report renderer, demo script, backup video. Builds against fixtures from H1, integrates real backend at H14.

Coordination contract: the JSON schema is locked at H1. Schema changes after H4 require both teammates to agree.

## 15. Demo flow (target 3 min)

The demo needs to land two stories: Nemotron's autonomous reasoning (Nemotron track) and NemoClaw's policy enforcement (NemoClaw track). Both must be visible.

1. **Problem framing (20s).** Patient goes home with 6 medications. 15 pairs to check. No way to know what's risky. Set up the stakes from the patient's perspective.
2. **Input + fan-out (40s).** Enter the medication list as a patient would (brand names, generics mixed). Hit submit, agent graph lights up. "Three sources, three types of evidence, queried in parallel. Each call goes through NemoClaw's policy layer." Briefly show one log line of an allowed call. (Serves NemoClaw.)
3. **Synthesis moment (50s).** The intellectual peak. Show Nemotron reasoning visibly. Highlight a real source disagreement. Show the reasoning trace, not just the answer. "Source A says X, source B says Y, here's the reconciliation." (Serves Nemotron.)
4. **Report (20s).** Plain-language patient view by default — what's risky, how serious, what to ask your doctor. Toggle to detailed view showing citations and severity scores.
5. **NemoClaw enforcement moment (20s).** Trigger a deliberately crafted input attempting an off-whitelist call. OpenShell blocks it. Log shows the block. "This is patient health data. Without NemoClaw, a prompt injection could exfiltrate it. With NemoClaw, it's a logged denial." (Serves NemoClaw.)
6. **Memory close (30s).** Add a new prescription. Only the new pairs re-query. Updated plain-language report in seconds. (Serves Nemotron via multi-step workflow with state.)

Pre-cache results for the demo cases in case of API latency. The cache is honest (real results from real queries) just retrieved locally for demo speed.

### Demo case selection
- **Primary case:** real polypharmacy regimen with 6 drugs, includes at least one pair where sources disagree (the synthesis moment depends on this)
- **Attack case:** crafted input designed to trigger an off-whitelist API call (the NemoClaw moment depends on this, prepare this before H21)
- **Follow-up case:** the regimen plus one additional drug, for the memory demo

## 16. Judge Q&A prep

Two audiences. Have crisp answers for each track's likely questions.

### Nemotron track questions
- **Why multi-agent instead of one big prompt?** Specialization, parallelism. Each source has different format / coverage / update cycles. The synthesis agent's job is reasoning, not retrieval.
- **Why Nemotron specifically?** Designed for agentic workflows including function calling, multi-step reasoning, and multi-agent orchestration. We use `nemotron-3-super-120b-a12b` for synthesis because the reasoning trace quality on structured medical text is what carries the cross-source reconciliation. Source agents can use the smaller `nemotron-3-nano-30b-a3b` if latency matters.
- **Where's the autonomous decision-making?** The synthesis agent decides which source to weight when sources disagree, decides when to flag a "predicted but unverified" risk, and decides how to translate clinical findings into plain language a patient can act on.
- **Show me the agent thinking.** The synthesis reasoning trace is exposed in the detailed view. Judges can see the chain of thought, not just the conclusion.
- **Why patient-facing and not just for clinicians?** Patients are the ones who go home with the regimen. Clinicians have DrugBank and Micromedex. Patients have Google. This closes that gap.

### NemoClaw track questions
- **Why NemoClaw and not just OpenClaw?** Patient medication data is sensitive. NemoClaw enforces an API whitelist (no exfiltration), filesystem containment (no host access), no shell execution (prompt injection containment), and audit logging. Without these, a malicious prompt injection in a FAERS event description could exfiltrate patient data. With NemoClaw, that attack surface is closed at the runtime level.
- **Show me the policy.** The YAML policy is in the repo and on screen during the demo.
- **What does the audit log look like?** Every tool call is logged. We show one query's full log in the demo.
- **Could you do this with just OS-level sandboxing?** You could, but you'd be writing custom containment per deployment. NemoClaw gives us policy-as-config that travels with the agent across local, DGX Spark, and cloud deployments.

### Shared questions
- **What's the false positive rate?** Not measured in 24h. Would require clinical validation against a held-out set of known interactions. This is a research prototype.
- **Why these sources?** Heterogeneous epistemic types: regulatory, empirical, predictive/curated. Each compensates for the others' gaps.
- **What would production look like?** FHIR integration for regimen ingestion, paid DrugBank or Micromedex for the curated source, NemoClaw on DGX Spark at the point of care, full audit log retention.
- **Hardest technical part?** Prompting synthesis to reason about source disagreement instead of silently summarizing. That's where the intelligence lives.

## 17. Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Third source (whichever we pick) doesn't work day-of | Medium | Pre-validate before hackathon, have fallback ready |
| Synthesis prompt drifts (hallucinates citations or miscalibrates severity) | High | Test against 3 fixed cases continuously, lock prompt by H13 |
| OpenFDA rate limits hit during demo | Low | Cache demo case results, fall back to cached on rate limit |
| OpenClaw memory layer flaky | Medium | Test memory demo end-to-end by H17, have non-memory backup demo |
| NemoClaw preview blocks integration entirely | Medium | Allocate 3h + 1h buffer. Cloud track ships independently if NemoClaw fails. |
| NemoClaw eats more than 4 hours | Medium | Hard cutoff at H18. If not working, document the attempt and pivot to polishing Cloud submission. |
| Demo crashes live on stage | Medium | Backup videos recorded by H21 for both tracks |
| Schema changes late in build | Low if disciplined | Lock at H1, require both teammates to agree on any post-H4 change |

## 18. Open questions

- Which third source? (Decagon, ChemBERTa, TWOSIDES, or some combination)
- Frontend design: needs separate pre-hackathon design pass (see section 11)
- Frontend styling approach (CSS modules, vanilla CSS, CSS-in-JS)
- Brev Launchable with bundled Nemotron, or OpenRouter API for inference? (Affects NemoClaw network whitelist)
- Do we need PubChem if our third source doesn't use SMILES?
- How do we cite findings in the patient view without exposing technical jargon?
- What's the exact severity rubric the synthesis agent uses (need to ground this in something real, not invent it)?
- Demo case selection: which three pairs best showcase source disagreement? Which attack case best demonstrates the NemoClaw block?

These get resolved before H7 of the build. Frontend design and NemoClaw access specifically need to be locked at H0.
