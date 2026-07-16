import { StockData, ChartData, CryptoData } from '../types/financial';

// All market data now comes from our own backend, which holds the upstream API
// keys server-side and caches responses. In dev, Vite proxies /api → the backend
// (see vite.config.ts). In prod, set VITE_API_BASE to the deployed backend URL.
const API_BASE = import.meta.env.VITE_API_BASE || '';

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// Minimal client-side fallback for when the backend itself is unreachable. The
// backend already returns fallback data on upstream errors, so this only kicks
// in if the backend is completely down.
const FALLBACK_STOCKS: StockData[] = [
  { symbol: 'AAPL', name: 'Apple Inc.', price: 175.43, change: 2.15, changePercent: 1.24, volume: 45234567, high: 176.8, low: 173.2, marketCap: 2.78e12 },
  { symbol: 'GOOGL', name: 'Alphabet Inc.', price: 142.56, change: -1.23, changePercent: -0.86, volume: 23456789, high: 144.2, low: 141.8, marketCap: 1.8e12 },
  { symbol: 'MSFT', name: 'Microsoft Corp.', price: 378.85, change: 5.67, changePercent: 1.52, volume: 32145698, high: 380.45, low: 375.2, marketCap: 2.81e12 },
];

const FALLBACK_CRYPTO: CryptoData[] = [
  { id: 'bitcoin', symbol: 'btc', name: 'Bitcoin', current_price: 43250.67, price_change_24h: 1250.34, price_change_percentage_24h: 2.98, market_cap: 8.47e11, total_volume: 2.35e10, high_24h: 43800, low_24h: 42100.5 },
  { id: 'ethereum', symbol: 'eth', name: 'Ethereum', current_price: 2634.89, price_change_24h: -45.23, price_change_percentage_24h: -1.69, market_cap: 3.16e11, total_volume: 1.23e10, high_24h: 2689.45, low_24h: 2598.3 },
];

export const financialApi = {
  async getStocks(): Promise<StockData[]> {
    try {
      return await getJson<StockData[]>('/api/stocks');
    } catch (error) {
      console.warn('Backend unreachable, using fallback stocks:', error);
      return FALLBACK_STOCKS;
    }
  },

  async getCrypto(): Promise<CryptoData[]> {
    try {
      return await getJson<CryptoData[]>('/api/crypto');
    } catch (error) {
      console.warn('Backend unreachable, using fallback crypto:', error);
      return FALLBACK_CRYPTO;
    }
  },

  async getHistoricalData(symbol: string, days: number = 30): Promise<ChartData[]> {
    try {
      return await getJson<ChartData[]>(`/api/history?symbol=${encodeURIComponent(symbol)}&days=${days}`);
    } catch (error) {
      console.warn(`Backend unreachable for history ${symbol}:`, error);
      return [];
    }
  },

  async searchStocks(query: string): Promise<StockData[]> {
    try {
      return await getJson<StockData[]>(`/api/search?q=${encodeURIComponent(query)}`);
    } catch (error) {
      console.warn('Search failed:', error);
      return [];
    }
  },
};
