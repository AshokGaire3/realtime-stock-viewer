import {
  CryptoData,
  HistorySeries,
  PredictionResult,
  StockData,
} from '../types/financial';

// All market data comes from our own backend, which holds the upstream API keys
// server-side and does the caching + fallback. The browser never talks to Alpha
// Vantage / Finnhub / CoinGecko directly — that's what leaked the keys before.
//
// Dev: leave VITE_API_BASE unset; vite proxies /api → the backend.
// Prod: set VITE_API_BASE to the deployed backend origin.
const API_BASE = import.meta.env.VITE_API_BASE || '';

async function getJson<T>(path: string, params: Record<string, string | number> = {}): Promise<T> {
  const query = new URLSearchParams(
    Object.entries(params).map(([key, value]) => [key, String(value)]),
  ).toString();

  const response = await fetch(`${API_BASE}/api${path}${query ? `?${query}` : ''}`);
  if (!response.ok) {
    // FastAPI reports errors as {detail: string} — surface it when present so
    // e.g. an unknown ticker shows "Unknown symbol: ZZZZZ" rather than "404".
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === 'string' ? body.detail : `${response.status} ${response.statusText}`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

// No client-side fallback data on purpose: the backend already serves labelled
// fallbacks when upstream fails. Inventing prices here would produce numbers
// with no `source`, i.e. demo data indistinguishable from a live quote.
export const financialApi = {
  getStocks: () => getJson<StockData[]>('/stocks'),
  getQuote: (symbol: string) => getJson<StockData>('/quote', { symbol }),
  getCrypto: () => getJson<CryptoData[]>('/crypto'),
  getHistory: (symbol: string, days = 30) => getJson<HistorySeries>('/history', { symbol, days }),
  searchStocks: (q: string) => getJson<StockData[]>('/search', { q }),
  getPrediction: (symbol: string, horizon = 7) =>
    getJson<PredictionResult>('/predict', { symbol, horizon }),
};
