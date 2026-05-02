'use client';

import { Moon, Search, Sun } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useTheme } from '@/lib/use-theme';

interface Props {
  hstNow?: string;
  islandFilter: string;
  islands: { value: string; label: string }[];
  onIslandFilter: (v: string) => void;
  streamConnected?: boolean;
  lastEventAt?: Date | null;
  onOpenSearch?: () => void;
}

export function Header({
  hstNow,
  islandFilter,
  islands,
  onIslandFilter,
  streamConnected,
  lastEventAt,
  onOpenSearch,
}: Props) {
  const [now, setNow] = useState(hstNow ?? '');
  const [agoLabel, setAgoLabel] = useState('');
  const { theme, toggle: toggleTheme } = useTheme();
  const pathname = usePathname() ?? '/';

  useEffect(() => {
    function recompute() {
      if (!lastEventAt) {
        setAgoLabel('');
        return;
      }
      const secs = Math.max(0, Math.round((Date.now() - lastEventAt.getTime()) / 1000));
      if (secs < 5) setAgoLabel('just now');
      else if (secs < 60) setAgoLabel(`${secs}s ago`);
      else if (secs < 3600) setAgoLabel(`${Math.round(secs / 60)}m ago`);
      else setAgoLabel(`${Math.round(secs / 3600)}h ago`);
    }
    recompute();
    const id = setInterval(recompute, 5000);
    return () => clearInterval(id);
  }, [lastEventAt]);

  useEffect(() => {
    const tick = () => {
      const fmt = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Pacific/Honolulu',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      setNow(fmt.format(new Date()));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header
      className="sticky top-0 z-40 flex h-[64px] items-center justify-between gap-3 border-b border-line bg-gradient-to-b from-bg-2 to-bg-1 px-4 backdrop-blur-md sm:h-[78px] sm:px-8"
    >
      <div className="flex min-w-0 items-center gap-3 sm:gap-[18px]">
        <div
          className="flex h-[38px] w-[38px] flex-shrink-0 items-center justify-center rounded-[12px] text-[18px] font-bold"
          style={{
            background: 'linear-gradient(135deg, var(--gold), var(--accent))',
            color: 'var(--text-on-accent)',
            boxShadow: '0 0 calc(20px * var(--glow)) oklch(0.80 0.12 85 / 0.35)',
          }}
        >
          ◈
        </div>
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold tracking-[-0.01em] sm:text-[18px]">
            Atrium <span className="text-text-3 font-normal">Network</span>
          </div>
          <div
            className="mono mt-[2px] hidden truncate text-[11px] text-text-3 sm:block"
            style={{ letterSpacing: '0.12em' }}
          >
            COMMON AREA MONITOR · HST {now}
          </div>
        </div>
      </div>

      <nav className="hidden gap-7 text-[13px] xl:flex">
        {([
          { label: 'Overview', href: '/' },
          { label: 'Properties', href: '/properties' },
          { label: 'Admin', href: '/admin' },
        ] as { label: string; href: string }[]).map((t) => {
          // Active = exact path match for '/', otherwise prefix match so
          // /properties/13 also lights up the Properties tab.
          const active =
            t.href === '/' ? pathname === '/' : pathname === t.href || pathname.startsWith(`${t.href}/`);
          return (
          <Link
            key={t.label}
            href={t.href}
            className={`relative cursor-pointer py-[6px] no-underline ${
              active ? 'font-semibold text-text-0' : 'font-medium text-text-2'
            }`}
          >
            {t.label}
            {active && (
              <span
                className="absolute inset-x-0 -bottom-[22px] h-[2px]"
                style={{
                  background: 'linear-gradient(90deg, var(--gold), var(--accent))',
                  boxShadow: '0 0 calc(8px * var(--glow)) var(--accent)',
                }}
              />
            )}
          </Link>
          );
        })}
      </nav>

      <div className="flex items-center gap-2 sm:gap-[14px]">
        {(agoLabel || streamConnected !== undefined) && (
          <span
            className="mono hidden items-center gap-2 text-[11px] text-text-3 md:inline-flex"
            title={streamConnected ? 'Live stream connected' : 'Live stream disconnected — polling fallback'}
            style={{ letterSpacing: '0.08em' }}
          >
            <span
              className="inline-block h-[6px] w-[6px] rounded-full"
              style={{
                background: streamConnected ? 'var(--ok)' : 'var(--text-3)',
                boxShadow: streamConnected
                  ? '0 0 calc(6px * var(--glow)) var(--ok)'
                  : 'none',
              }}
            />
            {agoLabel ? `Updated · ${agoLabel}` : streamConnected ? 'Live' : 'Polling'}
          </span>
        )}
        <button
          type="button"
          onClick={onOpenSearch}
          className="flex h-[36px] w-[36px] items-center justify-center gap-2 rounded-full border border-line bg-bg-1 text-text-3 transition-colors hover:border-line-strong hover:text-text-2 md:w-[220px] md:justify-start md:rounded-m md:px-3 md:text-[13px] lg:w-[280px]"
          aria-label="Open search palette"
        >
          <Search size={14} />
          <span className="hidden flex-1 text-left md:inline">Search properties, networks…</span>
          <span
            className="mono hidden rounded-s border border-line px-[6px] py-[1px] text-[10px] text-text-3 md:inline"
            aria-hidden
          >
            ⌘K
          </span>
        </button>

        <select
          value={islandFilter}
          onChange={(e) => onIslandFilter(e.target.value)}
          className="rounded-full border border-line-strong bg-transparent px-[14px] py-[6px] text-[12px] text-text-1"
          style={{ fontFamily: 'inherit' }}
          aria-label="Filter by island"
        >
          <option value="all">All Islands</option>
          {islands.map((i) => (
            <option key={i.value} value={i.value}>
              {i.label}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          className="flex h-[30px] w-[30px] items-center justify-center rounded-full border border-line text-text-2 transition-colors hover:border-line-strong hover:text-text-0"
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>

        <div
          className="flex h-[30px] w-[30px] items-center justify-center rounded-full text-[11px] font-bold"
          style={{
            background: 'linear-gradient(135deg, var(--accent), var(--gold))',
            color: 'var(--text-on-accent)',
          }}
        >
          JG
        </div>
      </div>
    </header>
  );
}
