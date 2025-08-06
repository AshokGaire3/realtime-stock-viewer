import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Bitcoin, Search, RefreshCw, Settings } from 'lucide-react';
import { StockCard } from './components/StockCard';
import { CryptoCard } from './components/CryptoCard';
import { PriceChart } from './components/PriceChart';
import { MarketOverview } from './components/MarketOverview';
import { SearchBar } from './components/SearchBar';
import { FilterControls } from './components/FilterControls';
import { ApiStatus } from './components/ApiStatus';
import { DataSourceInfo } from './components/DataSourceInfo';
import { financialApi } from './services/financialApi';
import { StockData, CryptoData } from './types/financial';

function App() {
  const [stocks, setStocks] = useState<StockData[]>([]);
  const [crypto, setCrypto] = useState<CryptoData[]>([]);
  const [selectedStock, setSelectedStock] = useState<string>('AAPL');
  const [activeTab, setActiveTab] = useState<'overview' | 'stocks' | 'crypto' | 'charts'>('overview');
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [apiError, setApiError] = useState<string>('');
  const [isLiveData, setIsLiveData] = useState(false);
  
  // Filter and sort states
  const [sortBy, setSortBy] = useState<'symbol' | 'price' | 'change' | 'volume'>('change');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [filterBy, setFilterBy] = useState<'all' | 'gainers' | 'losers'>('all');

  const fetchData = async () => {
    setLoading(true);
    setApiError('');
    try {
      const [stockData, cryptoData] = await Promise.all([
        financialApi.getStocks(),
        financialApi.getCrypto(),
      ]);
      setStocks(stockData);
      setCrypto(cryptoData);
      setLastUpdated(new Date());
      
      // Check if we're getting live data (basic heuristic)
      const hasApiKey = import.meta.env.VITE_ALPHA_VANTAGE_API_KEY && 
                       import.meta.env.VITE_ALPHA_VANTAGE_API_KEY !== 'demo';
      setIsLiveData(hasApiKey || stockData.length > 6);
      
    } catch (error) {
      console.error('Failed to fetch data:', error);
      setApiError(error instanceof Error ? error.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    // Auto-refresh data every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleSortChange = (newSortBy: typeof sortBy, newSortOrder: typeof sortOrder) => {
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
  };

  const getFilteredAndSortedStocks = () => {
    let filtered = stocks;
    
    if (filterBy === 'gainers') {
      filtered = stocks.filter(stock => stock.changePercent > 0);
    } else if (filterBy === 'losers') {
      filtered = stocks.filter(stock => stock.changePercent < 0);
    }

    return filtered.sort((a, b) => {
      let aValue: number | string = a[sortBy];
      let bValue: number | string = b[sortBy];
      
      if (sortBy === 'symbol') {
        aValue = a.symbol;
        bValue = b.symbol;
        return sortOrder === 'asc' 
          ? aValue.localeCompare(bValue as string)
          : (bValue as string).localeCompare(aValue);
      }
      
      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortOrder === 'asc' ? aValue - bValue : bValue - aValue;
      }
      
      return 0;
    });
  };

  const tabs = [
    { id: 'overview', label: 'Market Overview', icon: BarChart3 },
    { id: 'stocks', label: 'Stocks', icon: TrendingUp },
    { id: 'crypto', label: 'Crypto', icon: Bitcoin },
    { id: 'charts', label: 'Charts', icon: BarChart3 },
  ] as const;

  const filteredStocks = getFilteredAndSortedStocks();

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-white">FinanceHub</h1>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="hidden md:block">
                <SearchBar onSelectStock={setSelectedStock} />
              </div>
              
              <DataSourceInfo />
              
              <button
                onClick={fetchData}
                disabled={loading}
                className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-5 h-5 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
              </button>
              
              <div className="hidden lg:block">
                <ApiStatus isLive={isLiveData} lastUpdated={lastUpdated} error={apiError} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Search */}
      <div className="md:hidden p-4 bg-gray-800 border-b border-gray-700">
        <SearchBar onSelectStock={setSelectedStock} />
        <div className="mt-3">
          <ApiStatus isLive={isLiveData} lastUpdated={lastUpdated} error={apiError} />
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-4 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-gray-400 hover:text-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && (
          <div>
            <MarketOverview stocks={stocks} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div>
                <h2 className="text-2xl font-bold text-white mb-6">Top Stocks</h2>
                <div className="grid grid-cols-1 gap-4">
                  {stocks.slice(0, 3).map((stock) => (
                    <StockCard key={stock.symbol} stock={stock} onClick={setSelectedStock} />
                  ))}
                </div>
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white mb-6">Top Crypto</h2>
                <div className="grid grid-cols-1 gap-4">
                  {crypto.slice(0, 3).map((cryptoItem) => (
                    <CryptoCard key={cryptoItem.id} crypto={cryptoItem} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'stocks' && (
          <div>
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-3xl font-bold text-white">Stock Market</h2>
              <div className="text-sm text-gray-400">
                {filteredStocks.length} of {stocks.length} stocks
              </div>
            </div>
            
            <FilterControls
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSortChange={handleSortChange}
              filterBy={filterBy}
              onFilterChange={setFilterBy}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredStocks.map((stock) => (
                <StockCard key={stock.symbol} stock={stock} onClick={setSelectedStock} />
              ))}
            </div>
          </div>
        )}

        {activeTab === 'crypto' && (
          <div>
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-3xl font-bold text-white">Cryptocurrency Market</h2>
              <div className="text-sm text-gray-400">
                {crypto.length} cryptocurrencies
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {crypto.map((cryptoItem) => (
                <CryptoCard key={cryptoItem.id} crypto={cryptoItem} />
              ))}
            </div>
          </div>
        )}

        {activeTab === 'charts' && (
          <div>
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-3xl font-bold text-white">Price Charts</h2>
              <div className="text-sm text-gray-400">
                Viewing {selectedStock}
              </div>
            </div>
            
            <div className="grid grid-cols-1 gap-8">
              <PriceChart symbol={selectedStock} />
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {stocks.slice(0, 4).map((stock) => (
                  <button
                    key={stock.symbol}
                    onClick={() => setSelectedStock(stock.symbol)}
                    className={`p-4 rounded-xl border transition-all ${
                      selectedStock === stock.symbol
                        ? 'bg-blue-900/30 border-blue-500'
                        : 'bg-gray-800 border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <div className="text-white font-semibold">{stock.symbol}</div>
                    <div className="text-gray-400 text-sm">{stock.name}</div>
                    <div className="text-white text-lg mt-2">${stock.price.toFixed(2)}</div>
                    <div className={`text-sm ${stock.changePercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-3 text-gray-400">
              <RefreshCw className="w-6 h-6 animate-spin" />
              <span className="text-lg">Loading market data...</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-400 space-y-2">
            <p className="text-lg font-semibold text-white">FinanceHub - Live Financial Data Dashboard</p>
            <p className="text-sm">
              Real-time market data powered by Alpha Vantage, Finnhub, and CoinGecko APIs
            </p>
            <div className="flex justify-center items-center gap-4 text-xs">
              <ApiStatus isLive={isLiveData} lastUpdated={lastUpdated} error={apiError} />
            </div>
            <p className="text-xs text-gray-500 pt-2">
              * This dashboard is for educational purposes. Not financial advice.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;