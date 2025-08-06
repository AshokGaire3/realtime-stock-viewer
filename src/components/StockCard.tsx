import React from 'react';
import { TrendingUp, TrendingDown, DollarSign, BarChart3 } from 'lucide-react';
import { StockData } from '../types/financial';

interface StockCardProps {
  stock: StockData;
  onClick?: (symbol: string) => void;
}

export const StockCard: React.FC<StockCardProps> = ({ stock, onClick }) => {
  const isPositive = stock.change >= 0;
  const formatPrice = (price: number) => `$${price.toFixed(2)}`;
  const formatChange = (change: number) => `${change >= 0 ? '+' : ''}${change.toFixed(2)}`;
  const formatPercent = (percent: number) => `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  const formatVolume = (volume: number) => {
    if (volume >= 1000000) return `${(volume / 1000000).toFixed(1)}M`;
    if (volume >= 1000) return `${(volume / 1000).toFixed(1)}K`;
    return volume.toString();
  };

  return (
    <div 
      className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-gray-600 transition-all duration-300 cursor-pointer hover:transform hover:scale-105"
      onClick={() => onClick?.(stock.symbol)}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold text-white">{stock.symbol}</h3>
          <p className="text-gray-400 text-sm">{stock.name}</p>
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
          <span className="text-2xl font-bold text-white">{formatPrice(stock.price)}</span>
          <div className={`text-sm font-medium ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
            <div>{formatChange(stock.change)}</div>
            <div>{formatPercent(stock.changePercent)}</div>
          </div>
        </div>

        <div className="flex justify-between text-sm text-gray-400">
          <div className="flex items-center gap-1">
            <BarChart3 className="w-4 h-4" />
            <span>Vol: {formatVolume(stock.volume)}</span>
          </div>
          <div className="flex items-center gap-1">
            <DollarSign className="w-4 h-4" />
            <span>H: {formatPrice(stock.high)} L: {formatPrice(stock.low)}</span>
          </div>
        </div>

        <div className="w-full bg-gray-700 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all duration-500 ${
              isPositive ? 'bg-gradient-to-r from-green-600 to-green-400' : 'bg-gradient-to-r from-red-600 to-red-400'
            }`}
            style={{ width: `${Math.min(Math.abs(stock.changePercent) * 10, 100)}%` }}
          ></div>
        </div>
      </div>
    </div>
  );
};