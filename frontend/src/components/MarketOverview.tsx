import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, DollarSign, BarChart3 } from 'lucide-react';
import { StockData } from '../types/financial';
import { financialApi } from '../services/financialApi';

interface MarketOverviewProps {
  stocks: StockData[];
}

export const MarketOverview: React.FC<MarketOverviewProps> = ({ stocks }) => {
  const [marketData, setMarketData] = useState({
    totalMarketCap: 0,
    gainersCount: 0,
    losersCount: 0,
    averageChange: 0,
    topGainer: null as StockData | null,
    topLoser: null as StockData | null,
  });

  useEffect(() => {
    if (stocks.length === 0) return;

    const gainers = stocks.filter(stock => stock.changePercent > 0);
    const losers = stocks.filter(stock => stock.changePercent < 0);
    const totalMarketCap = stocks.reduce((sum, stock) => sum + (stock.marketCap || 0), 0);
    const averageChange = stocks.reduce((sum, stock) => sum + stock.changePercent, 0) / stocks.length;
    
    const topGainer = stocks.reduce((prev, current) => 
      (current.changePercent > prev.changePercent) ? current : prev
    );
    
    const topLoser = stocks.reduce((prev, current) => 
      (current.changePercent < prev.changePercent) ? current : prev
    );

    setMarketData({
      totalMarketCap,
      gainersCount: gainers.length,
      losersCount: losers.length,
      averageChange,
      topGainer,
      topLoser,
    });
  }, [stocks]);

  const formatMarketCap = (value: number) => {
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    return `$${(value / 1e6).toFixed(2)}M`;
  };

  const isMarketUp = marketData.averageChange > 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div className="p-2 bg-blue-900/30 rounded-lg">
            <DollarSign className="w-6 h-6 text-blue-400" />
          </div>
          <div className={`text-sm ${isMarketUp ? 'text-green-400' : 'text-red-400'}`}>
            {isMarketUp ? '+' : ''}{marketData.averageChange.toFixed(2)}%
          </div>
        </div>
        <div className="text-2xl font-bold text-white mb-1">
          {formatMarketCap(marketData.totalMarketCap)}
        </div>
        <div className="text-gray-400 text-sm">Total Market Cap</div>
      </div>

      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div className="p-2 bg-green-900/30 rounded-lg">
            <TrendingUp className="w-6 h-6 text-green-400" />
          </div>
          <div className="text-sm text-green-400">
            {((marketData.gainersCount / stocks.length) * 100).toFixed(0)}%
          </div>
        </div>
        <div className="text-2xl font-bold text-white mb-1">
          {marketData.gainersCount}
        </div>
        <div className="text-gray-400 text-sm">Gainers Today</div>
      </div>

      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div className="p-2 bg-red-900/30 rounded-lg">
            <TrendingDown className="w-6 h-6 text-red-400" />
          </div>
          <div className="text-sm text-red-400">
            {((marketData.losersCount / stocks.length) * 100).toFixed(0)}%
          </div>
        </div>
        <div className="text-2xl font-bold text-white mb-1">
          {marketData.losersCount}
        </div>
        <div className="text-gray-400 text-sm">Losers Today</div>
      </div>

      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div className="p-2 bg-purple-900/30 rounded-lg">
            <BarChart3 className="w-6 h-6 text-purple-400" />
          </div>
          <div className="text-sm text-purple-400">
            Live
          </div>
        </div>
        <div className="text-2xl font-bold text-white mb-1">
          {stocks.length}
        </div>
        <div className="text-gray-400 text-sm">Assets Tracked</div>
      </div>

      {marketData.topGainer && (
        <div className="bg-gray-800 rounded-xl p-6 border border-green-700/50 md:col-span-2">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-green-900/30 rounded-lg">
              <TrendingUp className="w-5 h-5 text-green-400" />
            </div>
            <span className="text-green-400 font-semibold">Top Gainer</span>
          </div>
          <div className="flex justify-between items-center">
            <div>
              <div className="text-xl font-bold text-white">{marketData.topGainer.symbol}</div>
              <div className="text-gray-400 text-sm">{marketData.topGainer.name}</div>
            </div>
            <div className="text-right">
              <div className="text-xl font-bold text-white">
                ${marketData.topGainer.price.toFixed(2)}
              </div>
              <div className="text-green-400 font-semibold">
                +{marketData.topGainer.changePercent.toFixed(2)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {marketData.topLoser && (
        <div className="bg-gray-800 rounded-xl p-6 border border-red-700/50 md:col-span-2">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-red-900/30 rounded-lg">
              <TrendingDown className="w-5 h-5 text-red-400" />
            </div>
            <span className="text-red-400 font-semibold">Top Loser</span>
          </div>
          <div className="flex justify-between items-center">
            <div>
              <div className="text-xl font-bold text-white">{marketData.topLoser.symbol}</div>
              <div className="text-gray-400 text-sm">{marketData.topLoser.name}</div>
            </div>
            <div className="text-right">
              <div className="text-xl font-bold text-white">
                ${marketData.topLoser.price.toFixed(2)}
              </div>
              <div className="text-red-400 font-semibold">
                {marketData.topLoser.changePercent.toFixed(2)}%
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};