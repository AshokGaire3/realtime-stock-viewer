import React from 'react';
import { Filter, SortAsc, SortDesc } from 'lucide-react';

interface FilterControlsProps {
  sortBy: 'symbol' | 'price' | 'change' | 'volume';
  sortOrder: 'asc' | 'desc';
  onSortChange: (sortBy: 'symbol' | 'price' | 'change' | 'volume', sortOrder: 'asc' | 'desc') => void;
  filterBy: 'all' | 'gainers' | 'losers';
  onFilterChange: (filter: 'all' | 'gainers' | 'losers') => void;
}

export const FilterControls: React.FC<FilterControlsProps> = ({
  sortBy,
  sortOrder,
  onSortChange,
  filterBy,
  onFilterChange,
}) => {
  const sortOptions = [
    { value: 'symbol', label: 'Symbol' },
    { value: 'price', label: 'Price' },
    { value: 'change', label: 'Change %' },
    { value: 'volume', label: 'Volume' },
  ] as const;

  const filterOptions = [
    { value: 'all', label: 'All Stocks', color: 'text-gray-400' },
    { value: 'gainers', label: 'Gainers', color: 'text-green-400' },
    { value: 'losers', label: 'Losers', color: 'text-red-400' },
  ] as const;

  return (
    <div className="flex flex-col sm:flex-row gap-4 mb-6">
      <div className="flex items-center gap-2 text-gray-400">
        <Filter className="w-5 h-5" />
        <span className="text-sm font-medium">Filter:</span>
      </div>
      
      <div className="flex flex-wrap gap-2">
        {filterOptions.map((option) => (
          <button
            key={option.value}
            onClick={() => onFilterChange(option.value)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filterBy === option.value
                ? 'bg-blue-600 text-white'
                : `bg-gray-800 ${option.color} hover:bg-gray-700`
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 ml-auto">
        <span className="text-sm font-medium text-gray-400">Sort by:</span>
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value as any, sortOrder)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
        >
          {sortOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        
        <button
          onClick={() => onSortChange(sortBy, sortOrder === 'asc' ? 'desc' : 'asc')}
          className="p-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
        >
          {sortOrder === 'asc' ? <SortAsc className="w-4 h-4" /> : <SortDesc className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};