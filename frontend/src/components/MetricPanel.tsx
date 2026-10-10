import React from 'react';

interface Props {
  label: string;
  value: React.ReactNode;
  hint?: string;
}

export const MetricPanel: React.FC<Props> = ({ label, value, hint }) => (
  <div className="bg-white border border-gh-border rounded-md px-3 py-2.5 min-w-0">
    <div className="text-xs font-medium text-gh-muted uppercase tracking-wide truncate">{label}</div>
    <div className="text-xl font-semibold text-gh-fg mt-0.5 tabular-nums truncate">{value}</div>
    {hint && <div className="text-xs text-gh-muted mt-0.5 truncate">{hint}</div>}
  </div>
);
