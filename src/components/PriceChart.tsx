import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ChartData } from '../types/financial';
import { financialApi } from '../services/financialApi';
import { format } from 'date-fns';
import { Loader2 } from 'lucide-react';

interface PriceChartProps {
  symbol: string;
  days?: number;
}

export const PriceChart: React.FC<PriceChartProps> = ({ symbol, days = 30 }) => {
  const [data, setData] = useState<ChartData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const chartData = await financialApi.getHistoricalData(symbol, days);
        setData(chartData);
      } catch (error) {
        console.error('Failed to fetch chart data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [symbol, days]);

  const formatTooltipValue = (value: number, name: string) => {
    if (name === 'price') return [`$${value.toFixed(2)}`, 'Price'];
    return [value, name];
  };

  const formatTooltipLabel = (label: string) => {
    return format(new Date(label), 'MMM dd, yyyy');
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 h-96 flex items-center justify-center">
        <div className="flex items-center gap-2 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading chart data...</span>
        </div>
      </div>
    );
  }

  const isPositiveTrend = data.length > 1 && data[data.length - 1].price > data[0].price;

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-xl font-bold text-white">{symbol} Price Chart</h3>
        <div className="flex gap-2">
          {[7, 30, 90].map((period) => (
            <button
              key={period}
              className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                days === period
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              {period}D
            </button>
          ))}
        </div>
      </div>

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis 
              dataKey="date" 
              stroke="#9CA3AF"
              fontSize={12}
              tickFormatter={(value) => format(new Date(value), 'MMM dd')}
            />
            <YAxis 
              stroke="#9CA3AF"
              fontSize={12}
              tickFormatter={(value) => `$${value.toFixed(0)}`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '8px',
                color: '#F9FAFB'
              }}
              formatter={formatTooltipValue}
              labelFormatter={formatTooltipLabel}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke={isPositiveTrend ? '#10B981' : '#EF4444'}
              strokeWidth={3}
              dot={false}
              activeDot={{ r: 6, fill: isPositiveTrend ? '#10B981' : '#EF4444' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};