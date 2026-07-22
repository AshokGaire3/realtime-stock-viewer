import React, { useEffect, useState } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { format } from 'date-fns';
import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { TodayShowcase as TodayShowcaseData } from '../types/financial';
import { financialApi } from '../services/financialApi';
import { DemoBadge } from './DemoBadge';

const ACTUAL = '#3B82F6';
const FORECAST = '#EC4899';

// New hourly bars only land on the hour; polling faster just re-serves the
// same 5-minute server cache (see predictions.py::TODAY_TTL).
const REFRESH_MS = 60_000;

interface Row {
  time: string;
  actual?: number;
  predicted?: number;
  band?: [number, number];
}

export const TodayShowcase: React.FC<{ symbol: string }> = ({ symbol }) => {
  const [data, setData] = useState<TodayShowcaseData | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const result = await financialApi.getTodayShowcase(symbol);
        if (cancelled) return;

        const actualRows: Row[] = result.bars.map((bar) => ({ time: bar.date, actual: bar.price }));
        const last = actualRows[actualRows.length - 1];
        if (last?.actual !== undefined) {
          last.predicted = last.actual;
          last.band = [last.actual, last.actual];
        }
        setRows([
          ...actualRows,
          ...result.forecast.map((point) => ({
            time: point.date,
            predicted: point.predicted,
            band: [point.lower, point.upper] as [number, number],
          })),
        ]);
        setData(result);
        setError('');
      } catch (err) {
        if (cancelled) return;
        console.error('Failed to load today showcase:', err);
        setError(err instanceof Error ? err.message : 'Failed to load today showcase');
        setData(null);
        setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    setLoading(true);
    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [symbol]);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 h-96 flex items-center justify-center">
        <div className="flex items-center gap-2 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading today's forecast for {symbol}...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 h-96 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 font-medium">{error}</p>
          <p className="text-gray-500 text-sm mt-1">
            No hourly data yet for {symbol} — it's collected by a scheduled job, not fetched on
            demand.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-bold text-white">{symbol} — {data.trading_date}</h3>
            {data.data_source === 'fallback' && (
              <DemoBadge title="Forecast fitted on simulated demo prices — not a market signal" />
            )}
            <span className="text-xs text-gray-500">model: {data.model}</span>
          </div>
        </div>

        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="time"
                stroke="#9CA3AF"
                fontSize={12}
                tickFormatter={(value) => format(new Date(value), 'HH:mm')}
              />
              <YAxis
                stroke="#9CA3AF"
                fontSize={12}
                domain={['dataMin', 'dataMax']}
                tickFormatter={(value) => `$${value.toFixed(0)}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: '8px',
                  color: '#F9FAFB',
                }}
                itemStyle={{ color: '#E5E7EB' }}
                labelFormatter={(label) => format(new Date(label), 'HH:mm')}
                formatter={(value, name) => {
                  if (name === '95% confidence' && Array.isArray(value)) {
                    return [`$${value[0].toFixed(2)} – $${value[1].toFixed(2)}`, name];
                  }
                  return [`$${Number(value).toFixed(2)}`, name];
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                formatter={(value) => <span className="text-gray-400">{value}</span>}
              />
              <Area
                dataKey="band"
                name="95% confidence"
                stroke="none"
                fill={FORECAST}
                fillOpacity={0.15}
                connectNulls
              />
              <Line
                dataKey="actual"
                name="Actual"
                stroke={ACTUAL}
                strokeWidth={2}
                dot={{ r: 3, fill: ACTUAL }}
                activeDot={{ r: 4, fill: ACTUAL }}
              />
              <Line
                dataKey="predicted"
                name="Forecast"
                stroke={FORECAST}
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
                activeDot={{ r: 4, fill: FORECAST }}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-700">
          <h4 className="text-sm font-semibold text-white">Today's predictions, labeled against reality</h4>
          <p className="text-xs text-gray-500 mt-1">
            Every hourly forecast this model made today, and what actually happened once that hour
            closed — this is the evidence that feeds back into which model gets served next.
          </p>
        </div>
        {data.scored.length === 0 ? (
          <p className="px-6 py-4 text-sm text-gray-500">
            No predictions logged yet today — the collector hasn't ticked since the last bar closed.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase">
                <th className="text-left px-6 py-2">As of</th>
                <th className="text-right px-6 py-2">Predicted</th>
                <th className="text-right px-6 py-2">Actual</th>
                <th className="text-right px-6 py-2">Error</th>
                <th className="text-right px-6 py-2">Direction</th>
              </tr>
            </thead>
            <tbody>
              {data.scored.map((row, i) => (
                <tr key={i} className="border-t border-gray-700/60">
                  <td className="px-6 py-2 text-gray-300">{format(new Date(row.as_of), 'HH:mm')}</td>
                  <td className="px-6 py-2 text-right text-gray-300">${row.predicted.toFixed(2)}</td>
                  <td className="px-6 py-2 text-right text-gray-300">
                    {row.actual !== null ? `$${row.actual.toFixed(2)}` : '—'}
                  </td>
                  <td className="px-6 py-2 text-right text-gray-300">
                    {row.abs_error !== null ? `$${row.abs_error.toFixed(2)}` : '—'}
                  </td>
                  <td className="px-6 py-2 text-right">
                    {row.direction_hit === null ? (
                      <span className="inline-flex items-center gap-1 text-gray-500">
                        <Clock className="w-3.5 h-3.5" /> pending
                      </span>
                    ) : row.direction_hit ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5" /> hit
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-red-400">
                        <XCircle className="w-3.5 h-3.5" /> miss
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-gray-500">
        {data.data_source === 'fallback' &&
          "This forecast was fitted on simulated demo prices, so the numbers above describe mock data, not the market. "}
        {data.disclaimer}
      </p>
    </div>
  );
};
