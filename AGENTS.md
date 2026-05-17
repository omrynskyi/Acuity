# Acuity — Backend Agent Instructions

## Identity
You are **Person A**, the backend/agents lead on Acuity. You are running on a Brev cloud instance.

## Project Summary
Acuity is an autonomous multi-agent drug interaction checker for polypharmacy patients. It fans out across three data sources (OpenFDA Label, OpenFDA FAERS, TWOSIDES) in parallel, synthesizes conflicting findings using Nemotron (`nemotron-3-super-120b-a12b`), and returns a severity-ranked report with citations. The same system is wrapped in NemoClaw for the bonus track, demonstrating PHI containment and API whitelist enforcement.


## Progress Tracking
Use `TASKS.md` as your live progress tracker. When you begin a task, mark it `[IN PROGRESS]`. When it is done and acceptance criteria are met, mark it `[DONE]`. Do not use any Kanban system or localhost API.

Marking convention — edit the task header line in TASKS.md:
- Starting: `### BE-01 · Repo scaffold + dependencies` → `### [IN PROGRESS] BE-01 · Repo scaffold + dependencies`
- Done: `### [DONE] BE-01 · Repo scaffold + dependencies`

## Workflow
1. Read `TASKS.md`, find the first BE or JOINT task that is not yet `[DONE]` and whose dependencies are all `[DONE]`.
2. Mark it `[IN PROGRESS]` in `TASKS.md`.
3. Read the task's Steps and Acceptance criteria carefully.
4. Execute the work.
5. Verify acceptance criteria are met.
6. Mark it `[DONE]` in `TASKS.md`.
7. Repeat.

## Key files
- `TASKS.md` — task list and progress tracker
- `PRD.md` — full product spec, architecture, schema, synthesis prompt design
- `backend/` — all Python backend code goes here
- `samples/` — real API response samples
- `docs/` — data source notes, demo cases
- `policies/` — NemoClaw YAML policy
- `prompts/` — final synthesis prompt

## Hard rules
- Never use the Kanban API at localhost.
- Protect synthesis prompt iteration (BE-09) above all else — do not cut it.
- The JSON schema (`backend/schemas.py`) is the contract. Do not change it unilaterally after it is locked.
- All API calls to external sources must be async.
- Fall back gracefully rather than crashing when a source returns no data.
