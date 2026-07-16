import React, { useState } from 'react';
import { Info, X, ExternalLink } from 'lucide-react';

export const DataSourceInfo: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="p-2 text-gray-400 hover:text-white transition-colors"
        title="Data Sources"
      >
        <Info className="w-5 h-5" />
      </button>

      {isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-xl p-6 max-w-md w-full border border-gray-700">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold text-white">Data Sources</h3>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-sm">
              <div>
                <h4 className="font-semibold text-white mb-2">Stock Market Data</h4>
                <div className="space-y-2 text-gray-300">
                  <div className="flex items-center justify-between">
                    <span>Alpha Vantage API</span>
                    <a
                      href="https://www.alphavantage.co/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Finnhub API (backup)</span>
                    <a
                      href="https://finnhub.io/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-white mb-2">Cryptocurrency Data</h4>
                <div className="flex items-center justify-between text-gray-300">
                  <span>CoinGecko API</span>
                  <a
                    href="https://www.coingecko.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>

              <div className="pt-4 border-t border-gray-700">
                <h4 className="font-semibold text-white mb-2">Setup Instructions</h4>
                <div className="text-gray-300 space-y-1">
                  <p>1. Get a free API key from Alpha Vantage</p>
                  <p>2. Copy <code className="text-blue-300">backend/.env.example</code> to <code className="text-blue-300">backend/.env</code></p>
                  <p>3. Add your API key there and restart the backend</p>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  Keys live on the server, never in the browser — this app requests all
                  market data through its own backend.
                </p>
              </div>

              <div className="text-xs text-gray-400 pt-2 border-t border-gray-700">
                <p>
                  * Without a key, the dashboard falls back to simulated demo data. Anything
                  synthetic is marked <span className="text-amber-300 font-medium">Demo</span> —
                  those prices are not real quotes.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};