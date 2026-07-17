import React from 'react';
import { Wifi, WifiOff, AlertTriangle, FlaskConical } from 'lucide-react';

interface ApiStatusProps {
  /** How many of the loaded quotes came back with source: 'live'. */
  liveCount: number;
  total: number;
  lastUpdated: Date;
  error?: string;
}

/**
 * Reports live-vs-demo from the backend's actual `source` tags. A list often
 * mixes both (e.g. the Alpha Vantage demo key only serves MSFT), so "partly
 * live" is a real state, not an edge case.
 */
export const ApiStatus: React.FC<ApiStatusProps> = ({ liveCount, total, lastUpdated, error }) => {
  const formatTime = (date: Date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const status = error
    ? { Icon: AlertTriangle, tone: 'text-red-400', label: error }
    : total === 0
      ? { Icon: WifiOff, tone: 'text-gray-400', label: 'No data' }
      : liveCount === 0
        ? { Icon: FlaskConical, tone: 'text-amber-400', label: 'Demo data' }
        : liveCount === total
          ? { Icon: Wifi, tone: 'text-green-400', label: 'Live data' }
          : { Icon: FlaskConical, tone: 'text-amber-400', label: `Partly live (${liveCount}/${total})` };

  return (
    <div className="flex items-center gap-2 text-sm">
      <status.Icon className={`w-4 h-4 ${status.tone}`} />
      <span className={status.tone}>{status.label}</span>
      <span className="text-gray-400">• Updated {formatTime(lastUpdated)}</span>
    </div>
  );
};
