'use client';

import { AlertTriangle, RotateCcw } from 'lucide-react';
import React from 'react';

interface Props {
  children: React.ReactNode;
  /** Display name shown in the fallback (e.g. "Properties") */
  label?: string;
  /** Optional retry handler — invalidate a query, refetch, etc. */
  onRetry?: () => void;
  /** Use the small inline variant instead of the full card */
  inline?: boolean;
}

interface State {
  error: Error | null;
}

/**
 * Per-card error boundary. Keeps a single card's render failure from
 * blanking the whole dashboard. React still requires class components for
 * `componentDidCatch`; everything else is hooks.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', this.props.label ?? 'card', error, info);
  }

  reset = () => {
    this.setState({ error: null });
    this.props.onRetry?.();
  };

  render() {
    if (this.state.error == null) return this.props.children;

    const message = this.state.error.message || 'Unexpected error';
    if (this.props.inline) {
      return (
        <div
          role="alert"
          className="flex items-center gap-3 rounded-l border border-bad bg-bad-soft px-3 py-2 text-[12px] text-text-1"
        >
          <AlertTriangle size={14} className="text-bad" aria-hidden />
          <span className="flex-1 truncate">{message}</span>
          <button
            type="button"
            onClick={this.reset}
            className="mono inline-flex items-center gap-1 text-[11px] text-text-2 hover:text-text-0"
          >
            <RotateCcw size={12} /> retry
          </button>
        </div>
      );
    }

    return (
      <div className="card flex flex-col items-center justify-center gap-3 p-8 text-center">
        <AlertTriangle size={20} className="text-bad" aria-hidden />
        <div className="text-[13px] font-medium text-text-1">
          {this.props.label ? `Couldn't load ${this.props.label}` : 'Something went wrong'}
        </div>
        <div className="mono text-[11px] text-text-3">{message}</div>
        <button
          type="button"
          onClick={this.reset}
          className="mt-1 inline-flex items-center gap-2 rounded-full border border-line-strong bg-transparent px-4 py-1.5 text-[12px] text-text-1 transition-colors hover:bg-bg-2"
        >
          <RotateCcw size={13} /> Retry
        </button>
      </div>
    );
  }
}
