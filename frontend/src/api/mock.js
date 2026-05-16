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

export async function streamAnalyzeRegimen(drugs, sessionId, { onEvent } = {}) {
  const data = await analyzeRegimen(drugs, sessionId);
  const delay = (ms) => new Promise((r) => setTimeout(r, ms));
  await delay(300);
  onEvent?.({ type: 'intake_done', data: { regimen: data.report.regimen, pairs: [], duration_ms: 280 } });
  await delay(150);
  onEvent?.({ type: 'memory_result', data: { total_pairs: data.report.interactions.length, new_pairs: [], cached_pairs: [], duration_ms: 1 } });
  for (const ix of data.report.interactions) {
    await delay(600);
    onEvent?.({ type: 'synthesis_result', data: { ...ix, cached: false, duration_ms: 580 } });
  }
  await delay(250);
  onEvent?.({ type: 'report_done', data: { session_id: data.session_id, report: data.report, durations_ms: {} } });
}
