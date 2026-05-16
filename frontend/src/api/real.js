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

export async function streamAnalyzeRegimen(drugs, sessionId, { onEvent, onError } = {}) {
  const res = await fetch(`${BASE}/api/analyze/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drugs, session_id: sessionId ?? undefined }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() ?? '';
    for (const frame of frames) {
      if (!frame.trim()) continue;
      let eventType = 'message';
      let dataLine = '';
      for (const line of frame.split('\n')) {
        if (line.startsWith('event: ')) eventType = line.slice(7).trim();
        else if (line.startsWith('data: ')) dataLine = line.slice(6);
      }
      if (!dataLine) continue;
      try {
        const payload = JSON.parse(dataLine);
        onEvent?.({ type: eventType, data: payload });
        if (eventType === 'error') onError?.(new Error(payload.detail || 'Stream error'));
      } catch (e) {
        console.warn('[SSE] Failed to parse frame:', dataLine, e);
      }
    }
  }
}
