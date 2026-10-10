import React from 'react';

export type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'accent';

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: 'bg-gh-canvas text-gh-muted border-gh-border',
  success: 'bg-gh-successSubtle text-gh-success border-gh-successBorder',
  warning: 'bg-gh-warningSubtle text-gh-warning border-gh-warningBorder',
  danger: 'bg-gh-dangerSubtle text-gh-danger border-gh-dangerBorder',
  accent: 'bg-gh-accentSubtle text-gh-accent border-gh-accentBorder',
};

interface Props {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<Props> = ({ variant = 'default', children, className = '' }) => (
  <span
    className={`inline-flex items-center px-2 py-0.5 rounded-md border text-xs font-medium leading-4 whitespace-nowrap ${VARIANT_CLASSES[variant]} ${className}`}
  >
    {children}
  </span>
);

/** Maps a risk/difficulty label already returned by the API to a badge color. Heuristic display mapping only — no new scoring logic. */
export function riskVariant(level: string): BadgeVariant {
  const l = (level || '').toUpperCase();
  if (l === 'HIGH' || l === 'HARD') return 'danger';
  if (l === 'MEDIUM' || l === 'MODERATE') return 'warning';
  if (l === 'LOW' || l === 'EASY') return 'success';
  return 'default';
}
