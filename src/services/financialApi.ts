import { StockData, ChartData, CryptoData } from '../types/financial';

// API Configuration
const ALPHA_VANTAGE_API_KEY = import.meta.env.VITE_ALPHA_VANTAGE_API_KEY || 'demo';
const ALPHA_VANTAGE_BASE_URL = 'https://www.alphavantage.co/query';
const COINGECKO_BASE_URL = 'https://api.coingecko.com/api/v3';
const FINNHUB_API_KEY = import.meta.env.VITE_FINNHUB_API_KEY;
const FINNHUB_BASE_URL = 'https://finnhub.io/api/v1';

// Popular stock symbols to track
const POPULAR_STOCKS = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'NFLX'];

// Cache to avoid hitting API limits
const cache = new Map<string, { data: any; timestamp: number }>();
const CACHE_DURATION = 60000; // 1 minute

const getCachedData = (key: string) => {
  const cached = cache.get(key);
  if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
    return cached.data;
  }
  return null;
};

const setCachedData = (key: string, data: any) => {
  cache.set(key, { data, timestamp: Date.now() });
};

// Fallback mock data for when APIs are unavailable or rate limited
const FALLBACK_STOCKS: StockData[] = [
  { symbol: 'AAPL', name: 'Apple Inc.', price: 175.43, change: 2.15, changePercent: 1.24, volume: 45234567, high: 176.80, low: 173.20, marketCap: 2780000000000 },
  { symbol: 'GOOGL', name: 'Alphabet Inc.', price: 142.56, change: -1.23, changePercent: -0.86, volume: 23456789, high: 144.20, low: 141.80, marketCap: 1800000000000 },
  { symbol: 'MSFT', name: 'Microsoft Corp.', price: 378.85, change: 5.67, changePercent: 1.52, volume: 32145698, high: 380.45, low: 375.20, marketCap: 2810000000000 },
  { symbol: 'TSLA', name: 'Tesla Inc.', price: 248.73, change: -8.45, changePercent: -3.29, volume: 89765432, high: 255.30, low: 246.90, marketCap: 790000000000 },
  { symbol: 'AMZN', name: 'Amazon.com Inc.', price: 155.89, change: 3.21, changePercent: 2.10, volume: 54321098, high: 157.45, low: 153.60, marketCap: 1620000000000 },
  { symbol: 'NVDA', name: 'NVIDIA Corp.', price: 875.25, change: 15.67, changePercent: 1.82, volume: 67890123, high: 882.40, low: 865.30, marketCap: 2150000000000 },
];

const FALLBACK_CRYPTO: CryptoData[] = [
  { id: 'bitcoin', symbol: 'BTC', name: 'Bitcoin', current_price: 43250.67, price_change_24h: 1250.34, price_change_percentage_24h: 2.98, market_cap: 847000000000, total_volume: 23456789000, high_24h: 43800.00, low_24h: 42100.50 },
  { id: 'ethereum', symbol: 'ETH', name: 'Ethereum', current_price: 2634.89, price_change_24h: -45.23, price_change_percentage_24h: -1.69, market_cap: 316000000000, total_volume: 12345678000, high_24h: 2689.45, low_24h: 2598.30 },
  { id: 'cardano', symbol: 'ADA', name: 'Cardano', current_price: 0.485, price_change_24h: 0.023, price_change_percentage_24h: 4.98, market_cap: 17200000000, total_volume: 567890123, high_24h: 0.492, low_24h: 0.461 },
  { id: 'solana', symbol: 'SOL', name: 'Solana', current_price: 98.34, price_change_24h: 5.67, price_change_percentage_24h: 6.12, market_cap: 42800000000, total_volume: 1234567890, high_24h: 101.23, low_24h: 95.78 },
];

// Utility function to handle API errors gracefully
const handleApiError = (error: any, fallbackData: any) => {
  console.warn('API request failed, using fallback data:', error.message);
  return fallbackData;
};

// Get stock quote from Alpha Vantage
const getStockQuote = async (symbol: string): Promise<StockData | null> => {
  const cacheKey = `stock_${symbol}`;
  const cached = getCachedData(cacheKey);
  if (cached) return cached;

  try {
    const url = `${ALPHA_VANTAGE_BASE_URL}?function=GLOBAL_QUOTE&symbol=${symbol}&apikey=${ALPHA_VANTAGE_API_KEY}`;
    const response = await fetch(url);
    const data = await response.json();

    if (data['Error Message'] || data['Note']) {
      throw new Error(data['Error Message'] || 'API rate limit exceeded');
    }

    const quote = data['Global Quote'];
    if (!quote) {
      throw new Error('No quote data available');
    }

    const stockData: StockData = {
      symbol: quote['01. symbol'],
      name: symbol, // We'll need to get company name separately
      price: parseFloat(quote['05. price']),
      change: parseFloat(quote['09. change']),
      changePercent: parseFloat(quote['10. change percent'].replace('%', '')),
      volume: parseInt(quote['06. volume']),
      high: parseFloat(quote['03. high']),
      low: parseFloat(quote['04. low']),
      marketCap: 0, // Would need separate API call
    };

    setCachedData(cacheKey, stockData);
    return stockData;
  } catch (error) {
    console.warn(`Failed to fetch stock data for ${symbol}:`, error);
    return null;
  }
};

// Get stock data from Finnhub (alternative/backup)
const getStockQuoteFinnhub = async (symbol: string): Promise<StockData | null> => {
  if (!FINNHUB_API_KEY) return null;

  const cacheKey = `finnhub_${symbol}`;
  const cached = getCachedData(cacheKey);
  if (cached) return cached;

  try {
    const [quoteResponse, profileResponse] = await Promise.all([
      fetch(`${FINNHUB_BASE_URL}/quote?symbol=${symbol}&token=${FINNHUB_API_KEY}`),
      fetch(`${FINNHUB_BASE_URL}/stock/profile2?symbol=${symbol}&token=${FINNHUB_API_KEY}`)
    ]);

    const quote = await quoteResponse.json();
    const profile = await profileResponse.json();

    if (quote.error || !quote.c) {
      throw new Error('Invalid quote data');
    }

    const stockData: StockData = {
      symbol: symbol,
      name: profile.name || symbol,
      price: quote.c,
      change: quote.d || 0,
      changePercent: quote.dp || 0,
      volume: 0, // Not available in this endpoint
      high: quote.h,
      low: quote.l,
      marketCap: profile.marketCapitalization * 1000000 || 0,
    };

    setCachedData(cacheKey, stockData);
    return stockData;
  } catch (error) {
    console.warn(`Failed to fetch Finnhub data for ${symbol}:`, error);
    return null;
  }
};

export const financialApi = {
  // Get current stock data
  async getStocks(): Promise<StockData[]> {
    const cacheKey = 'all_stocks';
    const cached = getCachedData(cacheKey);
    if (cached) return cached;

    try {
      const stockPromises = POPULAR_STOCKS.map(async (symbol) => {
        // Try Alpha Vantage first, then Finnhub as backup
        let stockData = await getStockQuote(symbol);
        if (!stockData) {
          stockData = await getStockQuoteFinnhub(symbol);
        }
        return stockData;
      });

      const results = await Promise.all(stockPromises);
      const validStocks = results.filter((stock): stock is StockData => stock !== null);

      // If we got some real data, use it; otherwise use fallback
      const finalData = validStocks.length > 0 ? validStocks : FALLBACK_STOCKS;
      setCachedData(cacheKey, finalData);
      return finalData;
    } catch (error) {
      return handleApiError(error, FALLBACK_STOCKS);
    }
  },

  // Get cryptocurrency data from CoinGecko
  async getCrypto(): Promise<CryptoData[]> {
    const cacheKey = 'crypto_data';
    const cached = getCachedData(cacheKey);
    if (cached) return cached;

    try {
      const url = `${COINGECKO_BASE_URL}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false&price_change_percentage=24h`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      const cryptoData: CryptoData[] = data.map((coin: any) => ({
        id: coin.id,
        symbol: coin.symbol,
        name: coin.name,
        current_price: coin.current_price,
        price_change_24h: coin.price_change_24h,
        price_change_percentage_24h: coin.price_change_percentage_24h,
        market_cap: coin.market_cap,
        total_volume: coin.total_volume,
        high_24h: coin.high_24h,
        low_24h: coin.low_24h,
      }));

      setCachedData(cacheKey, cryptoData);
      return cryptoData;
    } catch (error) {
      return handleApiError(error, FALLBACK_CRYPTO);
    }
  },

  // Get historical data for a specific symbol
  async getHistoricalData(symbol: string, days: number = 30): Promise<ChartData[]> {
    const cacheKey = `historical_${symbol}_${days}`;
    const cached = getCachedData(cacheKey);
    if (cached) return cached;

    try {
      // For crypto, use CoinGecko historical data
      if (['BTC', 'ETH', 'ADA', 'SOL'].includes(symbol.toUpperCase())) {
        const coinId = {
          'BTC': 'bitcoin',
          'ETH': 'ethereum',
          'ADA': 'cardano',
          'SOL': 'solana'
        }[symbol.toUpperCase()];

        if (coinId) {
          const url = `${COINGECKO_BASE_URL}/coins/${coinId}/market_chart?vs_currency=usd&days=${days}`;
          const response = await fetch(url);
          const data = await response.json();

          if (data.prices) {
            const chartData: ChartData[] = data.prices.map(([timestamp, price]: [number, number]) => ({
              date: new Date(timestamp).toISOString().split('T')[0],
              price: price,
              volume: 0, // Volume data would need separate processing
            }));

            setCachedData(cacheKey, chartData);
            return chartData;
          }
        }
      }

      // For stocks, try Alpha Vantage daily data
      const url = `${ALPHA_VANTAGE_BASE_URL}?function=TIME_SERIES_DAILY&symbol=${symbol}&apikey=${ALPHA_VANTAGE_API_KEY}`;
      const response = await fetch(url);
      const data = await response.json();

      if (data['Error Message'] || data['Note']) {
        throw new Error('API limit or error');
      }

      const timeSeries = data['Time Series (Daily)'];
      if (timeSeries) {
        const chartData: ChartData[] = Object.entries(timeSeries)
          .slice(0, days)
          .map(([date, values]: [string, any]) => ({
            date,
            price: parseFloat(values['4. close']),
            volume: parseInt(values['5. volume']),
          }))
          .reverse();

        setCachedData(cacheKey, chartData);
        return chartData;
      }

      throw new Error('No time series data available');
    } catch (error) {
      console.warn(`Failed to fetch historical data for ${symbol}:`, error);
      
      // Generate fallback historical data
      const fallbackData = generateFallbackHistoricalData(symbol, days);
      setCachedData(cacheKey, fallbackData);
      return fallbackData;
    }
  },

  // Search stocks by symbol or name
  async searchStocks(query: string): Promise<StockData[]> {
    try {
      // For demo purposes, search within our popular stocks
      const allStocks = await this.getStocks();
      return allStocks.filter(stock => 
        stock.symbol.toLowerCase().includes(query.toLowerCase()) ||
        stock.name.toLowerCase().includes(query.toLowerCase())
      );
    } catch (error) {
      console.warn('Search failed:', error);
      return [];
    }
  }
};

// Generate realistic fallback historical data
function generateFallbackHistoricalData(symbol: string, days: number): ChartData[] {
  const data: ChartData[] = [];
  const today = new Date();
  
  // Get base price from fallback stocks
  const baseStock = FALLBACK_STOCKS.find(s => s.symbol === symbol);
  const basePrice = baseStock ? baseStock.price : 100;
  
  for (let i = days; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    
    // Add some realistic price variation with trend
    const trendFactor = (days - i) / days; // Slight upward trend over time
    const randomVariation = (Math.random() - 0.5) * 0.05; // ±2.5% daily variation
    const price = basePrice * (0.95 + trendFactor * 0.1 + randomVariation);
    
    data.push({
      date: date.toISOString().split('T')[0],
      price: Math.round(price * 100) / 100,
      volume: Math.floor(Math.random() * 50000000) + 10000000
    });
  }
  
  return data;
}