import fixtures from '../data/fixtures.json';

export async function analyzeRegimen(_drugs, _sessionId) {
  await new Promise((r) => setTimeout(r, 2200));
  return {
    session_id: 'mock-session-' + Math.random().toString(36).slice(2, 8),
    report: fixtures.regimen_report,
  };
}

export function getSourceFindings() {
  return fixtures.source_findings;
}
