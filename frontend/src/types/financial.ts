// Mirrors backend/app/schemas.py — keep the two in sync; the client does no
// reshaping of API responses.

/** "live" = fetched from an upstream provider; "fallback" = synthetic demo data. */
export type Source = 'live' | 'fallback';

export interface StockData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap?: number;
  high: number;
  low: number;
  // Per-item: a list can mix live and fallback quotes when a provider only
  // partially responds.
  source: Source;
}

export interface ChartData {
  date: string;
  price: number;
  volume?: number;
}

export interface HistorySeries {
  symbol: string;
  source: Source;
  points: ChartData[];
}

export interface CryptoData {
  id: string;
  symbol: string;
  name: string;
  current_price: number;
  price_change_24h: number;
  price_change_percentage_24h: number;
  market_cap: number;
  total_volume: number;
  high_24h: number;
  low_24h: number;
  image: string | null;
  source: Source;
}

export interface Indicators {
  sma_20: number | null;
  sma_50: number | null;
  rsi_14: number | null;
  volatility: number | null;
}

export interface PredictionPoint {
  date: string;
  predicted: number;
  lower: number;
  upper: number;
}

/** Measured out-of-sample accuracy from the backtest — not a self-assessed score. */
export interface ModelAccuracy {
  horizon_days: number;
  /** Typical error at this horizon, percent. */
  mape: number;
  /** Random-walk ("price won't change") over the same origins. */
  baseline_mape: number;
  beats_baseline: boolean;
  n_forecasts: number;
}

export interface PredictionResult {
  symbol: string;
  model: string;
  generated_at: string;
  current_price: number;
  horizon_days: number;
  trend: 'up' | 'down' | 'flat';
  /** Null until a backtest has been run. */
  accuracy: ModelAccuracy | null;
  forecast: PredictionPoint[];
  indicators: Indicators;
  /** Whether the forecast was fitted on real prices. */
  data_source: Source;
  disclaimer: string;
}

export interface Portfolio {
  symbol: string;
  shares: number;
  avgCost: number;
  currentPrice: number;
}

export interface MarketSummary {
  totalValue: number;
  totalGain: number;
  totalGainPercent: number;
  topGainer: StockData;
  topLoser: StockData;
}
