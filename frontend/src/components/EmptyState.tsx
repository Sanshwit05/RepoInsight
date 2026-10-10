import React from 'react';
import { LucideIcon } from 'lucide-react';

interface Props {
  icon: LucideIcon;
  title: string;
  description: string;
}

export const EmptyState: React.FC<Props> = ({ icon: Icon, title, description }) => (
  <div className="bg-white border border-gh-border rounded-md min-h-[320px] flex flex-col items-center justify-center text-center px-6">
    <div className="w-10 h-10 rounded-md bg-gh-canvas border border-gh-border flex items-center justify-center mb-3">
      <Icon className="w-5 h-5 text-gh-muted" strokeWidth={1.75} />
    </div>
    <p className="text-sm font-medium text-gh-fg">{title}</p>
    <p className="text-xs text-gh-muted mt-1 max-w-sm">{description}</p>
  </div>
);
