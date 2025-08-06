import React, { useState, useRef, useEffect } from 'react';
import { Search, X } from 'lucide-react';
import { StockData } from '../types/financial';
import { financialApi } from '../services/financialApi';

interface SearchBarProps {
  onSelectStock: (symbol: string) => void;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSelectStock }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<StockData[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const searchStocks = async () => {
      if (query.length < 1) {
        setResults([]);
        setIsOpen(false);
        return;
      }

      setLoading(true);
      try {
        const searchResults = await financialApi.searchStocks(query);
        setResults(searchResults);
        setIsOpen(true);
      } catch (error) {
        console.error('Search failed:', error);
        setResults([]);
      } finally {
        setLoading(false);
      }
    };

    const debounceTimer = setTimeout(searchStocks, 300);
    return () => clearTimeout(debounceTimer);
  }, [query]);

  const handleSelectStock = (symbol: string) => {
    onSelectStock(symbol);
    setQuery('');
    setIsOpen(false);
  };

  const clearSearch = () => {
    setQuery('');
    setResults([]);
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={searchRef}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
        <input
          type="text"
          placeholder="Search stocks (AAPL, GOOGL, TSLA...)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full pl-10 pr-10 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-colors"
        />
        {query && (
          <button
            onClick={clearSearch}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-gray-800 border border-gray-700 rounded-xl shadow-xl z-50 max-h-96 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-gray-400">
              <div className="animate-pulse">Searching...</div>
            </div>
          ) : results.length > 0 ? (
            <div className="py-2">
              {results.map((stock) => (
                <button
                  key={stock.symbol}
                  onClick={() => handleSelectStock(stock.symbol)}
                  className="w-full px-4 py-3 text-left hover:bg-gray-700 transition-colors border-b border-gray-700/50 last:border-b-0"
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="text-white font-semibold">{stock.symbol}</div>
                      <div className="text-gray-400 text-sm">{stock.name}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-white">${stock.price.toFixed(2)}</div>
                      <div className={`text-sm ${stock.changePercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : query.length > 0 ? (
            <div className="p-4 text-center text-gray-400">
              No results found for "{query}"
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};