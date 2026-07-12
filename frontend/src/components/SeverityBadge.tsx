'use client';

import React from 'react';

interface SeverityBadgeProps {
  severity: 'High' | 'Medium' | 'Low';
}

const config = {
  High: {
    label: 'High',
    bg: 'bg-danger/15',
    text: 'text-danger',
    border: 'border-danger/25',
    dot: 'bg-danger',
  },
  Medium: {
    label: 'Medium',
    bg: 'bg-warning/15',
    text: 'text-warning',
    border: 'border-warning/25',
    dot: 'bg-warning',
  },
  Low: {
    label: 'Low',
    bg: 'bg-success/15',
    text: 'text-success',
    border: 'border-success/25',
    dot: 'bg-success',
  },
};

export default function SeverityBadge({ severity }: SeverityBadgeProps) {
  const c = config[severity] || config.Low;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${c.bg} ${c.text} ${c.border} border`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}