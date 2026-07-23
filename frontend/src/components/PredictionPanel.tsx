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
import { Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { PredictionResult } from '../types/financial';
import { financialApi } from '../services/financialApi';
import { TodayShowcase } from './TodayShowcase';

// Actual vs forecast is a categorical pair, validated for CVD separation against
// the dark surface (protan ΔE 14.7). The forecast is also dashed, so the two
// series are never distinguished by colour alone.
const ACTUAL = '#3B82F6';
const FORECAST = '#EC4899';

interface Row {
  date: string;
  actual?: number;
  predicted?: number;
  band?: [number, number];
}

const TrendIcon = ({ trend }: { trend: PredictionResult['trend'] }) =>
  trend === 'up' ? (
    <TrendingUp className="w-5 h-5 text-green-400" />
  ) : trend === 'down' ? (
    <TrendingDown className="w-5 h-5 text-red-400" />
  ) : (
    <Minus className="w-5 h-5 text-gray-400" />
  );

const Stat = ({ label, value }: { label: string; value: string }) => (
  <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
    <div className="text-gray-400 text-xs mb-1">{label}</div>
    <div className="text-white text-lg font-semibold">{value}</div>
  </div>
);

export const PredictionPanel: React.FC<{ symbol: string }> = ({ symbol }) => {
  const [view, setView] = useState<'daily' | 'today'>('daily');
  const [horizon, setHorizon] = useState(7);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const result = await financialApi.getPrediction(symbol, horizon);

        // Same response as the forecast — the history line and forecast line
        // can never disagree about what "now" is worth.
        const actualRows: Row[] = result.history.map((point) => ({ date: point.date, actual: point.price }));
        // Join the two lines at the seam: the last real price is also the
        // forecast's origin, with a zero-width band.
        const last = actualRows[actualRows.length - 1];
        if (last?.actual !== undefined) {
          last.predicted = last.actual;
          last.band = [last.actual, last.actual];
        }
        setRows([
          ...actualRows,
          ...result.forecast.map((point) => ({
            date: point.date,
            predicted: point.predicted,
            band: [point.lower, point.upper] as [number, number],
          })),
        ]);
        setPrediction(result);
      } catch (err) {
        console.error('Failed to load prediction:', err);
        setError(err instanceof Error ? err.message : 'Failed to load prediction');
        setPrediction(null);
        setRows([]);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [symbol, horizon]);

  const viewToggle = (
    <div className="flex gap-2">
      {(['daily', 'today'] as const).map((v) => (
        <button
          key={v}
          onClick={() => setView(v)}
          className={`px-3 py-1 rounded-lg text-sm transition-colors ${
            view === v ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
          }`}
        >
          {v === 'daily' ? 'Daily' : 'Today (Hourly)'}
        </button>
      ))}
    </div>
  );

  if (view === 'today') {
    return (
      <div className="space-y-6">
        {viewToggle}
        <TodayShowcase symbol={symbol} />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-6">
        {viewToggle}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 h-96 flex items-center justify-center">
          <div className="flex items-center gap-2 text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span>Running forecast for {symbol}...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !prediction) {
    return (
      <div className="space-y-6">
        {viewToggle}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 h-96 flex items-center justify-center">
          <div className="text-center">
            <p className="text-red-400 font-medium">{error}</p>
            <p className="text-gray-500 text-sm mt-1">No forecast available for {symbol}.</p>
          </div>
        </div>
      </div>
    );
  }

  const target = prediction.forecast[prediction.forecast.length - 1];
  const changePercent = ((target.predicted - prediction.current_price) / prediction.current_price) * 100;

  return (
    <div className="space-y-6">
      {viewToggle}
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-bold text-white">{symbol} Forecast</h3>
            <span className="text-xs text-gray-500">model: {prediction.model}</span>
          </div>
          <div className="flex gap-2">
            {[7, 14, 30].map((days) => (
              <button
                key={days}
                onClick={() => setHorizon(days)}
                className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                  horizon === days ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                {days}D
              </button>
            ))}
          </div>
        </div>

        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
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
                // Each row already names its series, so the value doesn't need to
                // wear the series colour to be identifiable.
                itemStyle={{ color: '#E5E7EB' }}
                labelFormatter={(label) => format(new Date(label), 'MMM dd, yyyy')}
                formatter={(value, name) => {
                  if (name === '95% confidence' && Array.isArray(value)) {
                    return [`$${value[0].toFixed(2)} – $${value[1].toFixed(2)}`, name];
                  }
                  return [`$${Number(value).toFixed(2)}`, name];
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                // Recharts tints legend labels with the series colour by default;
                // identity belongs to the swatch, text stays in the ink token.
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
                dot={false}
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

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-gray-400 text-xs mb-1">In {prediction.horizon_days} days</div>
          <div className="flex items-center gap-2">
            <TrendIcon trend={prediction.trend} />
            <span className="text-white text-lg font-semibold">${target.predicted.toFixed(2)}</span>
            <span className={`text-sm ${changePercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {changePercent >= 0 ? '+' : ''}
              {changePercent.toFixed(2)}%
            </span>
          </div>
        </div>
        <Stat
          label={`Typical error at ${prediction.horizon_days}d`}
          value={prediction.accuracy ? `±${prediction.accuracy.mape.toFixed(1)}%` : 'Not measured'}
        />
        <Stat label="RSI (14)" value={prediction.indicators.rsi_14?.toFixed(1) ?? '—'} />
        <Stat
          label="Volatility (annualized)"
          value={
            prediction.indicators.volatility !== null
              ? `${(prediction.indicators.volatility * 100).toFixed(1)}%`
              : '—'
          }
        />
      </div>

      {prediction.accuracy && !prediction.accuracy.beats_baseline && (
        <div className="bg-amber-950/40 border border-amber-800/60 rounded-xl p-4">
          <p className="text-amber-200 text-sm font-medium">Does not beat assuming the price stays flat.</p>
          <p className="text-amber-200/70 text-xs mt-1">
            {prediction.accuracy.mape.toFixed(1)}% avg error at {prediction.accuracy.horizon_days}d vs.{' '}
            {prediction.accuracy.baseline_mape.toFixed(1)}% for "no change," over{' '}
            {prediction.accuracy.n_forecasts.toLocaleString()} backtested forecasts.
          </p>
        </div>
      )}

      {prediction.accuracy && prediction.accuracy.beats_baseline && (
        <div className="bg-emerald-950/40 border border-emerald-800/60 rounded-xl p-4">
          <p className="text-emerald-200 text-sm font-medium">
            Measurably beats assuming the price stays flat (statistically significant, auto-selected).
          </p>
          <p className="text-emerald-200/70 text-xs mt-1">
            {prediction.accuracy.mape.toFixed(1)}% avg error at {prediction.accuracy.horizon_days}d vs.{' '}
            {prediction.accuracy.baseline_mape.toFixed(1)}% for "no change," over{' '}
            {prediction.accuracy.n_forecasts.toLocaleString()} backtested forecasts.
          </p>
        </div>
      )}

      <p className="text-xs text-gray-500">
        {!prediction.accuracy && 'Accuracy not yet measured for this model. '}
        {prediction.disclaimer}
      </p>
    </div>
  );
};
