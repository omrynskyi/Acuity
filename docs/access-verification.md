# Access verification — JOINT-00 results

**Date verified:** 2026-05-16, H0
**Verified by:** Person A (on Brev cloud instance)

## Network reachability (host shell)
All required data sources reachable, sub-400ms:

| Endpoint | Status | Time |
|---|---|---|
| `rxnav.nlm.nih.gov` (RxNorm) | 200 | 0.36s |
| `api.fda.gov/drug/label` (OpenFDA Label) | 200 | 0.28s |
| `api.fda.gov/drug/event` (OpenFDA FAERS) | 200 | 0.20s |
| `pubchem.ncbi.nlm.nih.gov` | 200 | 0.26s |
| `integrate.api.nvidia.com/v1/models` | 200 | 0.06s |

## NemoClaw / OpenShell
- `nemoclaw` v0.0.36 installed at `/usr/bin/nemoclaw`
- `openshell` v0.0.36 installed at `/usr/local/bin/openshell`
- Gateway `nemoclaw` running locally at `https://127.0.0.1:8080` (mTLS, certs in `~/.config/openshell/gateways/nemoclaw/mtls/`)
- Sandbox `nemoclaw` provisioned (default), `Phase: Ready`, agent `OpenClaw v2026.4.24`
- Inference provider `nvidia-prod` configured with `NVIDIA_API_KEY` credential (stored in OpenShell, not exposed to host env)
- Gateway-default model: `nvidia/nemotron-3-super-120b-a12b`
- Onboarded model: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (this is the nano variant — provider reports as reasoning model)
- Gateway inference route reports healthy: `https://integrate.api.nvidia.com/v1/models`

## Nemotron inference
The host shell has no NVIDIA_API_KEY exported. Two integration paths:

1. **Dev path (Phase 0-3):** export `NVIDIA_API_KEY` in `.env`, call `https://integrate.api.nvidia.com/v1` directly with an OpenAI-compatible client.
2. **Demo path (Phase 4):** run the backend inside the `nemoclaw` sandbox; OpenShell injects creds and routes inference through the gateway (which is what enforces the NemoClaw policy).

The synthesis agent code (BE-08) will be written to use a vanilla OpenAI client pointed at `OPENAI_BASE_URL` + `OPENAI_API_KEY` env vars so either path works without code changes.

## Action items for the human
- Drop `NVIDIA_API_KEY=…` into `Acuity/.env` so source-agent and synthesis development can run on the host. Provider already knows the key; OpenShell stores it under credential alias `NVIDIA_API_KEY` but does not export it to the shell.
- Decide whether Phase-4 demo runs the backend inside the `nemoclaw` sandbox (cleaner NemoClaw story) or alongside it on the host with the gateway proxying tool-restricted egress.

## Fallbacks if anything breaks
- Nemotron unreachable → use the OpenAI-compatible NVIDIA NIM provider (also configured under `nvidia-nim`) or an OpenRouter fallback.
- NemoClaw integration breaks → plain OpenClaw on host satisfies Cloud track per PRD §12 risk note.
