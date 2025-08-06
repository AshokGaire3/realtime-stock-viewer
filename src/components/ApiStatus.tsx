import React from 'react';
import { Wifi, WifiOff, AlertTriangle } from 'lucide-react';

interface ApiStatusProps {
  isLive: boolean;
  lastUpdated: Date;
  error?: string;
}

export const ApiStatus: React.FC<ApiStatusProps> = ({ isLive, lastUpdated, error }) => {
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="flex items-center gap-2 text-sm">
      {error ? (
        <>
          <AlertTriangle className="w-4 h-4 text-yellow-400" />
          <span className="text-yellow-400">Using cached data</span>
        </>
      ) : isLive ? (
        <>
          <Wifi className="w-4 h-4 text-green-400" />
          <span className="text-green-400">Live data</span>
        </>
      ) : (
        <>
          <WifiOff className="w-4 h-4 text-gray-400" />
          <span className="text-gray-400">Demo mode</span>
        </>
      )}
      <span className="text-gray-400">
        • Updated {formatTime(lastUpdated)}
      </span>
    </div>
  );
};