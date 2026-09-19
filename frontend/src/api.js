// Render is the shared backend for deployed and local frontend builds. Set
// VITE_API_BASE_URL to override it (for example, http://localhost:8000).
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'https://chotu-ai.onrender.com').replace(/\/$/, '');

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
