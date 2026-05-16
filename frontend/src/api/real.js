const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

export async function analyzeRegimen(drugs, sessionId) {
  const res = await fetch(`${BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drugs, session_id: sessionId ?? undefined }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export function getSourceFindings() {
  return [];
}
