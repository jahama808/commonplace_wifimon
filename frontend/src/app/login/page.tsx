'use client';

import { Loader2 } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next') || '/';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (res.status === 204) {
        router.push(next);
        router.refresh();
        return;
      }
      let detail: string | null = null;
      try {
        const body = await res.json();
        if (typeof body?.detail === 'string') detail = body.detail;
      } catch {
        /* non-JSON error */
      }
      setError(detail ?? `Login failed (${res.status})`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-0 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-3">
          <div
            className="flex h-[44px] w-[44px] items-center justify-center rounded-[12px] text-[20px] font-bold"
            style={{
              background: 'linear-gradient(135deg, var(--gold), var(--accent))',
              color: 'var(--text-on-accent)',
              boxShadow: '0 0 calc(20px * var(--glow)) oklch(0.80 0.12 85 / 0.35)',
            }}
            aria-hidden
          >
            ◈
          </div>
          <div>
            <div className="text-[18px] font-semibold tracking-[-0.01em]">
              Atrium <span className="font-normal text-text-3">Network</span>
            </div>
            <div
              className="mono text-[10.5px] text-text-3"
              style={{ letterSpacing: '0.14em' }}
            >
              COMMON AREA MONITOR
            </div>
          </div>
        </div>

        <form
          onSubmit={onSubmit}
          className="card mt-8 flex flex-col gap-4 p-6"
          noValidate
        >
          <div>
            <h1 className="text-[20px] font-semibold tracking-[-0.01em]">Sign in</h1>
            <p className="mt-1 text-[13px] text-text-2">
              Enter your operator credentials to continue.
            </p>
          </div>

          <Field
            id="username"
            label="Username"
            value={username}
            onChange={setUsername}
            autoComplete="username"
            autoFocus
            disabled={submitting}
          />
          <Field
            id="password"
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            disabled={submitting}
          />

          {error && (
            <div
              role="alert"
              className="rounded-m border border-bad bg-bad-soft px-3 py-2 text-[12.5px] text-text-1"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !username || !password}
            className="mt-2 inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            style={{
              background: 'linear-gradient(135deg, var(--gold), var(--accent))',
              color: 'var(--text-on-accent)',
              boxShadow: '0 0 calc(14px * var(--glow)) var(--accent-line)',
            }}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mono mt-6 text-center text-[10.5px] text-text-3">
          Sessions are signed cookies, valid for 14 days.
        </p>
      </div>
    </main>
  );
}

interface FieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: 'text' | 'password' | 'email';
  autoComplete?: string;
  autoFocus?: boolean;
  disabled?: boolean;
}

function Field({
  id,
  label,
  value,
  onChange,
  type = 'text',
  autoComplete,
  autoFocus,
  disabled,
}: FieldProps) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1">
      <span className="mono text-[10.5px] text-text-3" style={{ letterSpacing: '0.12em' }}>
        {label.toUpperCase()}
      </span>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        disabled={disabled}
        required
        className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[14px] text-text-0 outline-none transition-colors focus:border-accent disabled:opacity-60"
      />
    </label>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
