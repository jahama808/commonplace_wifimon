'use client';

interface Props {
  data: number[][]; // 7 rows × 24 columns, normalized 0..1 OR raw counts
  peak: { day: string; hour: number; count: number };
  quiet: { day: string; hour: number; count: number };
}

const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];

export function Heatmap({ data, peak, quiet }: Props) {
  // Normalize the grid in case the server sends raw counts
  let max = 0;
  for (const row of data) for (const v of row) if (v > max) max = v;
  const norm = max > 1 ? max : 1;

  return (
    <div className="card">
      <div className="card-hd border-b border-line">
        <div>
          <h3>24-Hour Activity Heatmap</h3>
          <div className="sub">DAY × HOUR · 7D</div>
        </div>
      </div>
      <div className="p-4">
        {/* Horizontal scroll container — on phones the 24-cell grid overflows;
            scrolling beats squishing cells too small to be readable. */}
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <div className="flex min-w-[480px] gap-[5px] sm:min-w-0">
            <div className="flex flex-col gap-[2px] pt-[14px]">
              {DAYS.map((d) => (
                <div
                  key={d}
                  className="mono flex items-center text-[9px] text-text-3"
                  style={{ height: 14, letterSpacing: '0.1em' }}
                >
                  {d}
                </div>
              ))}
            </div>
            <div className="flex-1">
              <div className="mono mb-1 flex justify-between text-[9px] text-text-3">
                {[0, 6, 12, 18, 23].map((h) => (
                  <span key={h}>{String(h).padStart(2, '0')}h</span>
                ))}
              </div>
              {data.map((row, ri) => (
                <div key={ri} className="mb-[2px] grid gap-[2px]" style={{ gridTemplateColumns: 'repeat(24, 1fr)' }}>
                  {row.map((v, ci) => {
                    const t = v / norm;
                    const c = `oklch(${(0.30 + t * 0.45).toFixed(3)} ${(0.05 + t * 0.13).toFixed(3)} ${(195 - t * 110).toFixed(0)})`;
                    return (
                      <div
                        key={ci}
                        title={`${DAYS[ri]} ${String(ci).padStart(2, '0')}:00 · ${Math.round(v)}`}
                        className="rounded-[3px] transition-transform duration-150 hover:scale-[1.15]"
                        style={{
                          height: 14,
                          background: c,
                          boxShadow: t > 0.7 ? `0 0 calc(4px * var(--glow)) ${c}` : 'none',
                        }}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <Callout label="PEAK" value={`${peak.day} ${String(peak.hour).padStart(2, '0')}:00`} sub={`${peak.count} devices`} />
          <Callout label="QUIET" value={`${quiet.day} ${String(quiet.hour).padStart(2, '0')}:00`} sub={`${quiet.count} devices`} />
        </div>
      </div>
    </div>
  );
}

function Callout({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-m border border-line bg-bg-2 px-3 py-[10px]">
      <div className="mono text-[10px] text-text-3" style={{ letterSpacing: '0.12em' }}>
        {label}
      </div>
      <div className="mt-[2px] text-[13px] font-medium text-text-1">{value}</div>
      <div className="mono mt-[2px] text-[11px] text-text-3">{sub}</div>
    </div>
  );
}
