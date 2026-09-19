// Use a same-origin `/api` request by default. Vite proxies this locally and
// vercel.json proxies it to Render in production, so browsers never need CORS.
// Set VITE_API_BASE_URL only when a direct API connection is intentionally needed.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`);
  return body;
}

export const money = (value) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
