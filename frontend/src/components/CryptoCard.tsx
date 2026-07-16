import React from 'react';
import { TrendingUp, TrendingDown, Bitcoin, DollarSign } from 'lucide-react';
import { CryptoData } from '../types/financial';

interface CryptoCardProps {
  crypto: CryptoData;
  onClick?: (symbol: string) => void;
}

export const CryptoCard: React.FC<CryptoCardProps> = ({ crypto, onClick }) => {
  const isPositive = crypto.price_change_24h >= 0;
  const formatPrice = (price: number) => {
    if (price < 1) return `$${price.toFixed(6)}`;
    if (price < 1000) return `$${price.toFixed(2)}`;
    return `$${price.toLocaleString()}`;
  };
  const formatChange = (change: number) => `${change >= 0 ? '+' : ''}${change.toFixed(2)}`;
  const formatPercent = (percent: number) => `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  const formatMarketCap = (marketCap: number) => {
    if (marketCap >= 1000000000000) return `$${(marketCap / 1000000000000).toFixed(2)}T`;
    if (marketCap >= 1000000000) return `$${(marketCap / 1000000000).toFixed(2)}B`;
    if (marketCap >= 1000000) return `$${(marketCap / 1000000).toFixed(2)}M`;
    return `$${marketCap.toLocaleString()}`;
  };

  return (
    <div 
      className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-yellow-500/50 transition-all duration-300 cursor-pointer hover:transform hover:scale-105"
      onClick={() => onClick?.(crypto.symbol)}
    >
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-yellow-500/20 rounded-lg">
            <Bitcoin className="w-5 h-5 text-yellow-400" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">{crypto.symbol.toUpperCase()}</h3>
            <p className="text-gray-400 text-sm">{crypto.name}</p>
          </div>
        </div>
        <div className={`p-2 rounded-lg ${isPositive ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
          {isPositive ? (
            <TrendingUp className="w-5 h-5 text-green-400" />
          ) : (
            <TrendingDown className="w-5 h-5 text-red-400" />
          )}
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-2xl font-bold text-white">{formatPrice(crypto.current_price)}</span>
          <div className={`text-sm font-medium text-right ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
            <div>{formatChange(crypto.price_change_24h)}</div>
            <div>{formatPercent(crypto.price_change_percentage_24h)}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm text-gray-400">
          <div>
            <div className="flex items-center gap-1 mb-1">
              <DollarSign className="w-3 h-3" />
              <span className="text-xs">Market Cap</span>
            </div>
            <div className="text-white font-medium">{formatMarketCap(crypto.market_cap)}</div>
          </div>
          <div>
            <div className="flex items-center gap-1 mb-1">
              <span className="text-xs">24h Volume</span>
            </div>
            <div className="text-white font-medium">{formatMarketCap(crypto.total_volume)}</div>
          </div>
        </div>

        <div className="flex justify-between text-xs text-gray-400">
          <span>24h High: {formatPrice(crypto.high_24h)}</span>
          <span>24h Low: {formatPrice(crypto.low_24h)}</span>
        </div>

        <div className="w-full bg-gray-700 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all duration-500 ${
              isPositive 
                ? 'bg-gradient-to-r from-green-600 to-green-400' 
                : 'bg-gradient-to-r from-red-600 to-red-400'
            }`}
            style={{ width: `${Math.min(Math.abs(crypto.price_change_percentage_24h) * 2, 100)}%` }}
          ></div>
        </div>
      </div>
    </div>
  );
};