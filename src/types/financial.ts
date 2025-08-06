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
}

export interface ChartData {
  date: string;
  price: number;
  volume?: number;
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