import React from 'react';
import { FlaskConical } from 'lucide-react';

/**
 * Marks synthetic data (`source: 'fallback'`). Demo prices must never be
 * mistakable for a live quote — see CLAUDE.md.
 */
export const DemoBadge: React.FC<{ title?: string }> = ({
  title = 'Simulated demo data — not a live market quote',
}) => (
  <span
    title={title}
    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-900/40 border border-amber-700/50 text-amber-300 text-xs font-medium"
  >
    <FlaskConical className="w-3 h-3" />
    Demo
  </span>
);
