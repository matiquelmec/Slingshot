import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'md' | 'lg';
  fullWidth?: boolean;
}

/**
 * Institutional Base UI Button
 * Standardized to Base-8 grid, WCAG 2.2 AA contrast (min 4.5:1),
 * and touch targets >= 44x44px for thumb-zone ergonomics.
 */
export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className = '',
  disabled,
  ...props
}) => {
  // Base classes ensure min-h-[44px] touch target (Fitts's Law + WCAG 2.2)
  const baseClasses =
    'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 min-h-[44px] min-w-[44px] select-none';

  // Base-8 spacing: px-4 (16px), py-2 (8px), gap-2 (8px)
  const sizeClasses = {
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-6 py-3 text-base gap-3 min-h-[48px]',
  }[size];

  // Contrast WCAG 2.2 AA compliant (> 4.5:1 on dark cyber palette)
  const variantClasses = {
    primary:
      'bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold focus:ring-emerald-400 disabled:bg-emerald-500/40 disabled:text-slate-900/60',
    secondary:
      'bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 focus:ring-slate-500 disabled:opacity-50',
    danger:
      'bg-rose-600 hover:bg-rose-700 text-white font-semibold focus:ring-rose-400 disabled:opacity-50',
    ghost:
      'bg-transparent hover:bg-slate-800/60 text-slate-200 focus:ring-slate-400 disabled:opacity-40',
  }[variant];

  const widthClass = fullWidth ? 'w-full' : '';

  return (
    <button
      className={`${baseClasses} ${sizeClasses} ${variantClasses} ${widthClass} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};
