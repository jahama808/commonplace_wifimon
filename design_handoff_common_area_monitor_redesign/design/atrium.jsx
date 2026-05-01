// Atrium — polished, hospitality-forward
// Adds: per-island summary tiles, stacked area chart, property detail drawer, off-peak quiet-hours indicator

const { useState, useMemo, useEffect } = React;

// ---------------- helpers ----------------
function pad(n) { return String(n).padStart(2, '0'); }

function Sparkline({ data, color = 'var(--accent)', height = 36, width = 120 }) {
  const max = Math.max(...data), min = Math.min(...data);
  const range = Math.max(1, max - min);
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const id = `sl-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.55" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${height} ${pts} ${width},${height}`} fill={`url(#${id})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

// ---------------- Header ----------------
function Header({ now, islandFilter, onIslandFilter, search, onSearch }) {
  return (
    <div style={{
      padding: '18px 36px',
      borderBottom: '1px solid var(--line)',
      background: 'linear-gradient(180deg, oklch(0.22 0.018 80), oklch(0.18 0.012 60))',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      position: 'sticky', top: 0, zIndex: 40,
      backdropFilter: 'blur(8px)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: 'linear-gradient(135deg, var(--gold), var(--accent))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--bg-0)', fontWeight: 700, fontSize: 17,
          boxShadow: '0 0 calc(20px * var(--glow)) oklch(0.80 0.12 85 / 0.35)',
        }}>◈</div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em' }}>
            Atrium <span style={{ color: 'var(--text-3)', fontWeight: 400, marginLeft: 4 }}>/ Network</span>
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', marginTop: 1 }}>
            COMMON AREA MONITOR
          </div>
        </div>
      </div>
      <nav style={{ display: 'flex', gap: 4 }}>
        {['Overview', 'Properties', 'Networks', 'Alerts', 'Reports'].map((t, i) => (
          <button key={t} style={{
            padding: '8px 16px', fontSize: 13, fontWeight: i === 0 ? 600 : 500,
            background: i === 0 ? 'var(--bg-2)' : 'transparent',
            color: i === 0 ? 'var(--text-0)' : 'var(--text-2)',
            border: '1px solid ' + (i === 0 ? 'var(--line-strong)' : 'transparent'),
            borderRadius: 8, cursor: 'pointer',
          }}>{t}</button>
        ))}
      </nav>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 999,
          padding: '6px 12px', minWidth: 200,
        }}>
          <span style={{ color: 'var(--text-3)', fontSize: 12 }}>⌕</span>
          <input value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search property, device…"
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: 'var(--text-0)', fontSize: 12, fontFamily: 'inherit' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)',
            border: '1px solid var(--line)', padding: '2px 5px', borderRadius: 4 }}>⌘K</span>
        </div>
        <select value={islandFilter} onChange={(e) => onIslandFilter(e.target.value)}
          style={{ background: 'var(--bg-2)', color: 'var(--text-1)', border: '1px solid var(--line)',
            borderRadius: 999, padding: '6px 14px', fontSize: 12, fontFamily: 'inherit' }}>
          <option value="all">All Islands</option>
          {window.ISLANDS.map(i => <option key={i} value={i}>{i}</option>)}
        </select>
        <div className="mono" style={{ fontSize: 12, color: 'var(--text-2)' }}>
          {now.h}:{now.m}:{now.s} <span style={{ color: 'var(--text-3)' }}>HST</span>
        </div>
        <div style={{ width: 30, height: 30, borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--accent), var(--gold))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: 'var(--bg-0)' }}>JG</div>
      </div>
    </div>
  );
}

// ---------------- Ticker ----------------
function Ticker({ alerts }) {
  const items = [...alerts, ...alerts];
  return (
    <div style={{ height: 34, display: 'flex', alignItems: 'center', overflow: 'hidden',
      background: 'oklch(0.18 0.012 60)', borderBottom: '1px solid var(--line)' }}>
      <div style={{ padding: '0 16px', fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
        letterSpacing: '0.18em', color: 'var(--accent)', borderRight: '1px solid var(--line)',
        height: '100%', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
        background: 'var(--bg-0)' }}>
        <span className="pulse-dot bad" style={{ width: 6, height: 6 }} />LIVE FEED
      </div>
      <div style={{ display: 'flex', gap: 36, animation: 'tickerScroll 65s linear infinite',
        whiteSpace: 'nowrap', paddingLeft: 36 }}>
        {items.map((a, i) => (
          <span key={i} style={{ fontSize: 12, fontFamily: 'var(--font-mono)',
            color: 'var(--text-2)', display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-3)' }}>{a.time}</span>
            <span style={{
              color: a.severity === 'critical' ? 'var(--bad)' : a.severity === 'warning' ? 'var(--warn)' : 'var(--accent)',
              fontWeight: 700, letterSpacing: '0.08em',
            }}>{a.severity.toUpperCase()}</span>
            <span style={{ color: 'var(--text-0)' }}>{a.property}</span>
            <span>· {a.message}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ---------------- Per-island summary tiles ----------------
function IslandTiles({ filter, onFilter }) {
  const stats = window.ISLANDS.map(name => {
    const props = window.PROPERTIES.filter(p => p.island === name);
    const offline = props.reduce((s, p) => s + (p.offlineCount || 0), 0);
    const devices = props.reduce((s, p) => s + p.devices, 0);
    const networks = props.reduce((s, p) => s + p.networks, 0);
    const status = offline > 0 ? (props.some(p => p.status === 'offline') ? 'offline' : 'degraded') : 'online';
    return { name, props: props.length, offline, devices, networks, status };
  });
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 18 }}>
      {stats.map(s => {
        const isActive = filter === s.name;
        const isAll = filter === 'all';
        return (
          <button key={s.name} onClick={() => onFilter(isActive ? 'all' : s.name)} style={{
            textAlign: 'left', cursor: 'pointer',
            padding: '16px 18px', borderRadius: 14,
            background: isActive ? 'var(--accent-soft)' : 'var(--bg-1)',
            border: '1px solid ' + (isActive ? 'var(--accent-line)' : 'var(--line)'),
            opacity: isAll || isActive ? 1 : 0.65,
            transition: 'all 0.2s',
            position: 'relative', overflow: 'hidden',
            fontFamily: 'inherit', color: 'inherit',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.14em',
                  fontFamily: 'var(--font-mono)' }}>{s.name.toUpperCase()}</div>
                <div style={{ fontSize: 22, fontWeight: 600, marginTop: 6, letterSpacing: '-0.01em' }}>
                  {s.props} <span style={{ fontSize: 13, color: 'var(--text-3)', fontWeight: 500 }}>properties</span>
                </div>
              </div>
              <span className={`pulse-dot ${s.status === 'online' ? 'ok' : s.status === 'degraded' ? 'warn' : 'bad'}`} />
            </div>
            <div style={{ display: 'flex', gap: 14, marginTop: 12, fontSize: 11, color: 'var(--text-2)' }}>
              <span><span className="mono" style={{ color: 'var(--text-1)', fontWeight: 600 }}>{s.networks}</span> nets</span>
              <span><span className="mono" style={{ color: 'var(--text-1)', fontWeight: 600 }}>{s.devices}</span> devices</span>
              {s.offline > 0 && (
                <span style={{ color: 'var(--bad)' }}>
                  <span className="mono" style={{ fontWeight: 600 }}>{s.offline}</span> offline
                </span>
              )}
            </div>
            {/* corner glow */}
            {s.status !== 'online' && (
              <div style={{ position: 'absolute', right: -20, top: -20, width: 80, height: 80, borderRadius: '50%',
                background: `radial-gradient(circle, ${s.status === 'offline' ? 'oklch(0.68 0.21 25 / 0.18)' : 'oklch(0.82 0.14 75 / 0.18)'}, transparent 70%)` }} />
            )}
          </button>
        );
      })}
    </div>
  );
}

// ---------------- Hero map ----------------
function HeroMap({ properties, onSelect, selected }) {
  const islands = {
    'Kauai':      { x: 0.12, y: 0.32, r: 0.10 },
    'Oahu':       { x: 0.32, y: 0.40, r: 0.11 },
    'Maui':       { x: 0.58, y: 0.32, r: 0.13 },
    'Big Island': { x: 0.82, y: 0.62, r: 0.16 },
  };
  const W = 900, H = 380;

  const onlineCount = properties.filter(p => p.status === 'online').length;
  const degradedCount = properties.filter(p => p.status === 'degraded').length;
  const offlineCount = properties.filter(p => p.status === 'offline').length;

  return (
    <div style={{
      position: 'relative', height: 420, borderRadius: 18, overflow: 'hidden',
      border: '1px solid var(--line)',
      background: 'radial-gradient(ellipse at 20% 20%, oklch(0.78 0.13 195 / 0.10), transparent 55%), radial-gradient(ellipse at 80% 80%, oklch(0.80 0.12 85 / 0.06), transparent 60%), oklch(0.18 0.012 60)',
    }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet" style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <pattern id="ocean-dots" width="18" height="18" patternUnits="userSpaceOnUse">
            <circle cx="9" cy="9" r="0.6" fill="oklch(0.45 0.012 60 / 0.35)" />
          </pattern>
          <radialGradient id="island-grad" cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor="oklch(0.40 0.025 80)" />
            <stop offset="100%" stopColor="oklch(0.24 0.015 80 / 0)" />
          </radialGradient>
        </defs>
        <rect width={W} height={H} fill="url(#ocean-dots)" />
        {Object.entries(islands).map(([name, isl]) => (
          <g key={name}>
            <ellipse cx={isl.x * W} cy={isl.y * H} rx={isl.r * W} ry={isl.r * W * 0.5}
              fill="url(#island-grad)" stroke="oklch(0.55 0.018 80 / 0.4)" strokeWidth="0.8" />
            <text x={isl.x * W} y={isl.y * H + isl.r * W * 0.5 + 22}
              textAnchor="middle" fontSize="11" fontFamily="var(--font-mono)"
              letterSpacing="0.18em" fill="var(--text-3)">{name.toUpperCase()}</text>
          </g>
        ))}
        {[40, 80, 130].map((r, i) => (
          <circle key={i} cx={islands.Oahu.x * W} cy={islands.Oahu.y * H} r={r} fill="none"
            stroke="var(--accent)" strokeWidth="0.5" strokeDasharray="2 5" opacity={0.25 - i * 0.06} />
        ))}
        {properties.map(p => {
          const cx = p.lng * W, cy = p.lat * H;
          const c = p.status === 'online' ? 'oklch(0.78 0.16 152)'
                  : p.status === 'degraded' ? 'oklch(0.82 0.14 75)'
                  : 'oklch(0.68 0.21 25)';
          const isSel = selected === p.id;
          return (
            <g key={p.id} style={{ cursor: 'pointer' }} onClick={() => onSelect(p.id)}>
              {p.status !== 'online' && (
                <circle cx={cx} cy={cy} r="20" fill="none" stroke={c} strokeWidth="1.2" opacity="0.6">
                  <animate attributeName="r" from="8" to="30" dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.7" to="0" dur="2s" repeatCount="indefinite" />
                </circle>
              )}
              <circle cx={cx} cy={cy} r={isSel ? 9 : 6} fill={c}
                style={{ filter: `drop-shadow(0 0 calc(8px * var(--glow)) ${c})` }} />
              <circle cx={cx} cy={cy} r={isSel ? 14 : 10} fill="none" stroke={c} strokeWidth="1" opacity="0.5" />
            </g>
          );
        })}
      </svg>
      <div style={{ position: 'absolute', top: 22, left: 26, right: 26,
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.14em',
            fontFamily: 'var(--font-mono)' }}>HAWAIIAN ISLANDS · LIVE</div>
          <div style={{ fontSize: 28, fontWeight: 600, marginTop: 6, letterSpacing: '-0.02em' }}>
            {properties.length} properties · {properties.reduce((s, p) => s + p.networks, 0)} networks
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>
            {properties.reduce((s, p) => s + p.devices, 0)} devices online · 14ms avg latency
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
          {offlineCount > 0 && <span className="badge-glow bad">{offlineCount} OUTAGE{offlineCount > 1 ? 'S' : ''}</span>}
          {degradedCount > 0 && <span className="badge-glow warn">{degradedCount} DEGRADED</span>}
          <span className="badge-glow ok">{onlineCount} ONLINE</span>
        </div>
      </div>
      <div style={{ position: 'absolute', bottom: 18, left: 26, fontFamily: 'var(--font-mono)',
        fontSize: 10, letterSpacing: '0.14em', color: 'var(--text-3)',
        display: 'flex', gap: 18 }}>
        <span>21.31°N · 157.86°W</span>
        <span>↑ N</span>
        <span>● UPDATED 12s</span>
      </div>
    </div>
  );
}

// ---------------- Property list grouped ----------------
function GroupedProperties({ properties, onSelect, selected }) {
  const grouped = window.ISLANDS
    .map(island => ({ island, props: properties.filter(p => p.island === island) }))
    .filter(g => g.props.length);

  return (
    <div className="card" style={{ gridColumn: 'span 8', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Properties</h3>
          <div className="sub">{properties.length} TOTAL · GROUPED BY ISLAND</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button style={chip(true)}>All</button>
          <button style={chip(false)}>Issues only</button>
          <button style={chip(false)}>Recently changed</button>
        </div>
      </div>
      {grouped.map(g => {
        const offline = g.props.reduce((s, p) => s + (p.offlineCount || 0), 0);
        return (
          <div key={g.island}>
            <div style={{
              padding: '11px 22px', background: 'var(--bg-2)', borderBottom: '1px solid var(--line)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 3, height: 14, borderRadius: 2,
                  background: 'linear-gradient(180deg, var(--gold), var(--accent))' }} />
                <span style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  {g.island}
                </span>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>
                  {g.props.length} · {g.props.reduce((s, p) => s + p.devices, 0)} devices
                </span>
              </div>
              {offline > 0 && <span className="badge-glow bad">{offline} OFFLINE</span>}
            </div>
            {g.props.map(p => {
              const sparkColor = p.status === 'online' ? 'var(--accent)' : p.status === 'degraded' ? 'var(--warn)' : 'var(--bad)';
              const isSel = selected === p.id;
              return (
                <div key={p.id} onClick={() => onSelect(p.id)} style={{
                  display: 'grid', gridTemplateColumns: '1.8fr 1fr 0.5fr 1.4fr 1fr',
                  padding: 'calc(13px * var(--density)) 22px',
                  alignItems: 'center', borderBottom: '1px solid var(--line)',
                  cursor: 'pointer',
                  background: isSel ? 'var(--accent-soft)' : 'transparent',
                  borderLeft: isSel ? '3px solid var(--accent)' : '3px solid transparent',
                  transition: 'background 0.15s',
                }}
                  onMouseEnter={e => !isSel && (e.currentTarget.style.background = 'var(--bg-2)')}
                  onMouseLeave={e => !isSel && (e.currentTarget.style.background = 'transparent')}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className={`pulse-dot ${p.status === 'online' ? 'ok' : p.status === 'degraded' ? 'warn' : 'bad'}`} />
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 500 }}>{p.name}</div>
                      <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{p.co}</div>
                    </div>
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-2)' }}>
                    {p.networks} {p.networks === 1 ? 'network' : 'networks'}
                  </div>
                  <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{p.devices}</div>
                  <div><Sparkline data={p.spark} color={sparkColor} /></div>
                  <div style={{ textAlign: 'right' }}>
                    {p.status === 'online' && <span className="badge-glow ok">ONLINE</span>}
                    {p.status === 'degraded' && <span className="badge-glow warn">{p.offlineCount} DEGRADED</span>}
                    {p.status === 'offline' && <span className="badge-glow bad">{p.offlineCount} OFFLINE</span>}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function chip(active) {
  return {
    padding: '6px 12px', fontSize: 11, fontWeight: 500,
    background: active ? 'var(--accent-soft)' : 'transparent',
    color: active ? 'var(--accent)' : 'var(--text-2)',
    border: '1px solid ' + (active ? 'var(--accent-line)' : 'var(--line)'),
    borderRadius: 999, cursor: 'pointer',
  };
}

// ---------------- Health sidebar ----------------
function HealthSidebar({ properties, alerts }) {
  const total = properties.reduce((s, p) => s + p.networks, 0);
  const offline = properties.reduce((s, p) => s + (p.offlineCount || 0), 0);
  const up = total - offline;
  const crit = alerts.filter(a => a.severity === 'critical');

  return (
    <div style={{ gridColumn: 'span 4', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Outage card */}
      <div className="card" style={{
        padding: 22, background: 'linear-gradient(135deg, oklch(0.68 0.21 25 / 0.14), var(--bg-1))',
        borderColor: 'oklch(0.68 0.21 25 / 0.35)',
        boxShadow: '0 0 calc(30px * var(--glow)) oklch(0.68 0.21 25 / calc(0.12 * var(--glow)))',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="pulse-dot bad" />
            <span style={{ fontSize: 11, letterSpacing: '0.16em', fontWeight: 700, color: 'var(--bad)' }}>ACTIVE OUTAGE</span>
          </div>
          <span className="mono" style={{ fontSize: 11, color: 'var(--bad)' }}>14m 32s</span>
        </div>
        <div style={{ fontSize: 22, fontWeight: 600, marginTop: 14, letterSpacing: '-0.01em' }}>{crit[0].property}</div>
        <div style={{ fontSize: 12.5, color: 'var(--text-2)', marginTop: 4 }}>{crit[0].network}</div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 8 }}>{crit[0].device}</div>
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button style={{
            flex: 1, padding: '9px 14px', fontSize: 12, fontWeight: 600,
            background: 'var(--bad)', color: 'oklch(0.18 0.012 60)', border: 'none',
            borderRadius: 8, cursor: 'pointer',
            boxShadow: '0 0 calc(12px * var(--glow)) oklch(0.68 0.21 25 / 0.45)',
          }}>Acknowledge</button>
          <button style={{
            flex: 1, padding: '9px 14px', fontSize: 12, fontWeight: 500,
            background: 'transparent', color: 'var(--text-1)',
            border: '1px solid var(--line-strong)', borderRadius: 8, cursor: 'pointer',
          }}>Dispatch</button>
        </div>
      </div>

      {/* KPIs */}
      <div className="card" style={{ padding: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Network Health</div>
          <span className="badge-glow accent">98.4% UPTIME 7D</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginTop: 14 }}>
          <KPI label="Networks Up" value={up} sub={`of ${total}`} color="var(--ok)" />
          <KPI label="Offline" value={offline} sub="across 2 sites" color="var(--bad)" critical={offline > 0} />
          <KPI label="Devices" value="781" sub="connected now" color="var(--accent)" />
          <KPI label="Latency" value="14ms" sub="avg, all hops" color="var(--gold)" mono />
        </div>
      </div>

      {/* Alerts feed */}
      <div className="card" style={{ padding: 0, flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
          <div>
            <h3>Live Alerts</h3>
            <div className="sub">{alerts.length} IN LAST 4H</div>
          </div>
          <span className="badge-glow accent">AUTO ▲</span>
        </div>
        <div style={{ flex: 1, overflow: 'auto', maxHeight: 420 }}>
          {alerts.map(a => (
            <div key={a.id} style={{
              padding: '12px 18px', borderBottom: '1px solid var(--line)',
              display: 'flex', flexDirection: 'column', gap: 4, cursor: 'pointer',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className={`badge-glow ${a.severity === 'critical' ? 'bad' : a.severity === 'warning' ? 'warn' : 'ok'}`}>
                  {a.severity === 'critical' ? 'CRIT' : a.severity === 'warning' ? 'WARN' : 'INFO'}
                </span>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{a.time}</span>
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-0)', fontWeight: 500 }}>{a.property}</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.4 }}>{a.message}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function KPI({ label, value, sub, color, critical, mono }) {
  return (
    <div style={{
      padding: '12px 14px', background: 'var(--bg-2)', borderRadius: 10,
      border: critical ? '1px solid oklch(0.68 0.21 25 / 0.45)' : '1px solid var(--line)',
      boxShadow: critical ? '0 0 calc(12px * var(--glow)) oklch(0.68 0.21 25 / calc(0.30 * var(--glow)))' : 'none',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>{label}</div>
      <div className={mono ? 'mono' : ''} style={{ fontSize: 22, fontWeight: 700, color, letterSpacing: '-0.01em', marginTop: 2 }}>{value}</div>
      <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 2 }}>{sub}</div>
    </div>
  );
}

// ---------------- Stacked area chart ----------------
function AreaChart({ ssid, onSsidChange, range, onRangeChange }) {
  const points = useMemo(() => window.genTimeSeries(
    ssid === 'all' ? 2 : 7, range === '7d' ? 168 : 24
  ), [ssid, range]);
  const max = Math.max(...points.map(p => p.total));
  const W = 800, H = 220;
  const pad = 8;

  const buildPath = (key, baseKey) => {
    let d = '';
    points.forEach((p, i) => {
      const x = (i / (points.length - 1)) * (W - pad * 2) + pad;
      const base = baseKey ? (p[baseKey] / max) * H : 0;
      const y = H - ((p[key] / max) * H + base);
      d += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1) + ' ';
    });
    return d;
  };
  const fillArea = (key, baseKey) => {
    const top = buildPath(key, baseKey);
    let d = top;
    for (let i = points.length - 1; i >= 0; i--) {
      const x = (i / (points.length - 1)) * (W - pad * 2) + pad;
      const base = baseKey ? (points[i][baseKey] / max) * H : 0;
      const y = H - base;
      d += 'L' + x.toFixed(1) + ',' + y.toFixed(1) + ' ';
    }
    return d + 'Z';
  };

  return (
    <div className="card" style={{ gridColumn: 'span 8', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Connected Devices</h3>
          <div className="sub">REFRESH IN 2m 52s · {ssid === 'all' ? 'ALL SSIDS' : ssid.toUpperCase()}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select value={ssid} onChange={(e) => onSsidChange(e.target.value)} style={{
            background: 'var(--bg-2)', color: 'var(--text-1)', border: '1px solid var(--line)',
            borderRadius: 999, padding: '5px 12px', fontSize: 11.5, fontFamily: 'inherit',
          }}>
            <option value="all">All SSIDs</option>
            {window.SSIDS.map(s => <option key={s}>{s}</option>)}
          </select>
          <div style={{ display: 'flex', background: 'var(--bg-2)', borderRadius: 999, padding: 2, border: '1px solid var(--line)' }}>
            {['1d', '7d'].map(r => (
              <button key={r} onClick={() => onRangeChange(r)} style={{
                padding: '4px 14px', fontSize: 11, fontWeight: 600, letterSpacing: '0.04em',
                background: range === r ? 'linear-gradient(135deg, var(--gold), var(--accent))' : 'transparent',
                color: range === r ? 'oklch(0.18 0.012 60)' : 'var(--text-2)',
                border: 'none', borderRadius: 999, cursor: 'pointer',
              }}>{r.toUpperCase()}</button>
            ))}
          </div>
        </div>
      </div>
      <div style={{ padding: '20px 22px 16px' }}>
        <svg viewBox={`0 0 ${W} ${H + 20}`} width="100%" height="240" style={{ display: 'block' }}>
          <defs>
            <linearGradient id="lobby-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.7" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.05" />
            </linearGradient>
            <linearGradient id="pool-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--gold)" stopOpacity="0.7" />
              <stop offset="100%" stopColor="var(--gold)" stopOpacity="0.05" />
            </linearGradient>
          </defs>
          {/* gridlines */}
          {[0.25, 0.5, 0.75].map(p => (
            <line key={p} x1={pad} x2={W - pad} y1={H * p} y2={H * p}
              stroke="var(--line)" strokeDasharray="2 4" />
          ))}
          {/* lobby area (bottom) */}
          <path d={fillArea('lobby')} fill="url(#lobby-grad)" />
          <path d={buildPath('lobby')} fill="none" stroke="var(--accent)" strokeWidth="1.5"
            style={{ filter: 'drop-shadow(0 0 calc(4px * var(--glow)) var(--accent))' }} />
          {/* pool stacked on top */}
          <path d={fillArea('pool', 'lobby')} fill="url(#pool-grad)" />
          <path d={buildPath('pool', 'lobby')} fill="none" stroke="var(--gold)" strokeWidth="1.5"
            style={{ filter: 'drop-shadow(0 0 calc(4px * var(--glow)) var(--gold))' }} />
          {/* y axis labels */}
          {[0, 0.25, 0.5, 0.75, 1].map(p => (
            <text key={p} x={W - 4} y={H * (1 - p) + 3} textAnchor="end"
              fontSize="9" fontFamily="var(--font-mono)" fill="var(--text-3)">
              {Math.round(max * p)}
            </text>
          ))}
        </svg>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4,
          fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)' }}>
          {['04/22', '04/23', '04/24', '04/25', '04/26', '04/27', '04/28'].map(d => <span key={d}>{d}</span>)}
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 14, fontSize: 11.5 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 10, height: 10, background: 'var(--accent)', borderRadius: 2,
              boxShadow: '0 0 calc(6px * var(--glow)) var(--accent)' }} /> Lobby / Front Desk
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 10, height: 10, background: 'var(--gold)', borderRadius: 2,
              boxShadow: '0 0 calc(6px * var(--glow)) var(--gold)' }} /> Pool / Bar
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------- Heatmap with quiet-hours indicator ----------------
function Heatmap({ data }) {
  const days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
  // Compute peak + quiet
  const flat = data.flat();
  const peakIdx = flat.indexOf(Math.max(...flat));
  const peakDay = Math.floor(peakIdx / 24), peakHour = peakIdx % 24;

  return (
    <div className="card" style={{ gridColumn: 'span 4', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Connection Heatmap</h3>
          <div className="sub">HOUR × DAY · 7D</div>
        </div>
      </div>
      <div style={{ padding: 16 }}>
        <div style={{ display: 'flex', gap: 5 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, paddingTop: 14 }}>
            {days.map(d => <div key={d} style={{
              height: 18, fontSize: 9, fontFamily: 'var(--font-mono)',
              color: 'var(--text-3)', letterSpacing: '0.1em',
              display: 'flex', alignItems: 'center',
            }}>{d}</div>)}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between',
              fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', marginBottom: 4 }}>
              {[0, 6, 12, 18, 23].map(h => <span key={h}>{pad(h)}h</span>)}
            </div>
            {data.map((row, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)',
                gap: 2, marginBottom: 2 }}>
                {row.map((v, j) => {
                  const hue = 195 - v * 110;
                  const c = `oklch(${0.30 + v * 0.45} ${0.05 + v * 0.13} ${hue})`;
                  return <div key={j} style={{
                    height: 18, background: c, borderRadius: 3,
                    boxShadow: v > 0.7 ? `0 0 calc(4px * var(--glow)) ${c}` : 'none',
                  }} />;
                })}
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div style={{ padding: '10px 12px', background: 'var(--bg-2)',
            borderRadius: 8, border: '1px solid var(--line)' }}>
            <div style={{ fontSize: 9.5, color: 'var(--text-3)', letterSpacing: '0.12em',
              fontFamily: 'var(--font-mono)' }}>PEAK</div>
            <div style={{ fontSize: 12, color: 'var(--text-1)', fontWeight: 600, marginTop: 2 }}>
              {days[peakDay]} {pad(peakHour)}:00
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 1 }}>412 devices</div>
          </div>
          <div style={{ padding: '10px 12px', background: 'var(--bg-2)',
            borderRadius: 8, border: '1px solid var(--line)' }}>
            <div style={{ fontSize: 9.5, color: 'var(--text-3)', letterSpacing: '0.12em',
              fontFamily: 'var(--font-mono)' }}>QUIET</div>
            <div style={{ fontSize: 12, color: 'var(--text-1)', fontWeight: 600, marginTop: 2 }}>
              03:00 – 06:00
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 1 }}>~32 devices</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------- Property detail drawer ----------------
function Drawer({ property, onClose }) {
  if (!property) return null;
  const series = useMemo(() => window.genTimeSeries(property.devices, 24, 4, 8, 8, 18), [property]);
  const max = Math.max(...series.map(s => s.total));
  const networks = [
    'Lobby / Front Desk', 'Pool / Front Desk / Bar', 'Spa & Wellness',
    'Conference', 'BBQ / Patio', 'Maintenance LAN',
  ].slice(0, property.networks);
  const devices = [
    { id: 'eero-pro-6e-lobby1', kind: 'eero Pro 6E', loc: 'Lobby Ceiling N', state: 'online', rssi: -52 },
    { id: 'eero-pro-6e-lobby2', kind: 'eero Pro 6E', loc: 'Lobby Ceiling S', state: 'online', rssi: -49 },
    { id: 'switch-core-01',     kind: 'Cisco SG350',  loc: 'IDF Closet',    state: property.status === 'offline' ? 'offline' : 'online', rssi: null },
    { id: 'eero-out-7-bbq',     kind: 'eero Outdoor 7', loc: 'BBQ Trellis',  state: 'online', rssi: -67 },
    { id: 'ap-pool-deck',       kind: 'eero Pro 6E', loc: 'Pool Deck',      state: 'online', rssi: -58 },
  ];

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 50,
      background: 'oklch(0.10 0 0 / 0.5)', backdropFilter: 'blur(4px)',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        position: 'absolute', right: 0, top: 0, bottom: 0, width: 520,
        background: 'var(--bg-1)', borderLeft: '1px solid var(--line)',
        boxShadow: '-30px 0 60px oklch(0.10 0 0 / 0.4)',
        overflow: 'auto',
        animation: 'slideIn 0.25s cubic-bezier(0.2, 0.8, 0.2, 1)',
      }}>
        {/* header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid var(--line)',
          background: 'linear-gradient(180deg, var(--bg-2), var(--bg-1))',
          position: 'sticky', top: 0, zIndex: 2,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.14em',
                fontFamily: 'var(--font-mono)' }}>{property.island.toUpperCase()}</div>
              <div style={{ fontSize: 22, fontWeight: 600, marginTop: 4, letterSpacing: '-0.01em' }}>
                {property.name}
              </div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-2)', marginTop: 4 }}>
                {property.co} · {property.networks} networks · {property.devices} devices
              </div>
            </div>
            <button onClick={onClose} style={{
              width: 32, height: 32, borderRadius: 8, border: '1px solid var(--line)',
              background: 'var(--bg-2)', color: 'var(--text-1)', cursor: 'pointer',
              fontSize: 14, fontFamily: 'inherit',
            }}>✕</button>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
            {property.status === 'online' && <span className="badge-glow ok">ALL ONLINE</span>}
            {property.status === 'degraded' && <span className="badge-glow warn">{property.offlineCount} DEGRADED</span>}
            {property.status === 'offline' && <span className="badge-glow bad">{property.offlineCount} OFFLINE</span>}
            <span className="badge-glow accent">98% UPTIME 7D</span>
          </div>
        </div>

        {/* mini chart */}
        <div style={{ padding: 24, borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600 }}>Devices · 24h</div>
            <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>peak {Math.max(...series.map(s=>s.total))} · now {series[series.length-1].total}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 80 }}>
            {series.map((p, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                <div style={{
                  height: (p.pool / max) * 80,
                  background: 'linear-gradient(180deg, var(--gold), oklch(0.65 0.13 70))',
                  borderRadius: '2px 2px 0 0',
                }} />
                <div style={{
                  height: (p.lobby / max) * 80,
                  background: 'linear-gradient(180deg, var(--accent), oklch(0.55 0.13 200))',
                }} />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4,
            fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
            <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>now</span>
          </div>
        </div>

        {/* networks */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.14em',
            fontFamily: 'var(--font-mono)', marginBottom: 10 }}>NETWORKS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {networks.map((n, i) => (
              <div key={n} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 8, border: '1px solid var(--line)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className={`pulse-dot ${i === 0 && property.status !== 'online' ? 'bad' : 'ok'}`} />
                  <span style={{ fontSize: 12.5, fontWeight: 500 }}>{n}</span>
                </div>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                  {Math.floor(property.devices / property.networks) + i} devices
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* devices */}
        <div style={{ padding: '16px 24px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.14em',
            fontFamily: 'var(--font-mono)', marginBottom: 10 }}>RECENT DEVICES</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {devices.map(d => (
              <div key={d.id} style={{
                display: 'grid', gridTemplateColumns: '12px 1fr auto auto',
                gap: 10, alignItems: 'center', padding: '8px 10px',
                borderRadius: 8, fontSize: 12,
              }}>
                <span className={`pulse-dot ${d.state === 'online' ? 'ok' : 'bad'}`} style={{ width: 6, height: 6 }} />
                <div>
                  <div style={{ fontSize: 12.5, color: 'var(--text-0)' }}>{d.kind}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{d.loc} · {d.id}</div>
                </div>
                <span className="mono" style={{ fontSize: 11, color: d.rssi && d.rssi > -60 ? 'var(--ok)' : d.rssi ? 'var(--warn)' : 'var(--text-3)' }}>
                  {d.rssi ? `${d.rssi} dBm` : '—'}
                </span>
                <span className={`badge-glow ${d.state === 'online' ? 'ok' : 'bad'}`}>
                  {d.state.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------- Root ----------------
function Atrium() {
  const [now, setNow] = useState({ h: '08', m: '56', s: '20' });
  const [islandFilter, setIslandFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [ssid, setSsid] = useState('all');
  const [range, setRange] = useState('7d');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const id = setInterval(() => {
      const d = new Date();
      setNow({ h: pad(d.getHours()), m: pad(d.getMinutes()), s: pad(d.getSeconds()) });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const filtered = useMemo(() => {
    let list = window.PROPERTIES;
    if (islandFilter !== 'all') list = list.filter(p => p.island === islandFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(p => p.name.toLowerCase().includes(q) || p.co.toLowerCase().includes(q));
    }
    return list;
  }, [islandFilter, search]);

  const heat = useMemo(() => window.genHeatmap(11), []);

  const selectProp = (id) => { setSelected(id); setDrawerOpen(true); };
  const selectedProp = window.PROPERTIES.find(p => p.id === selected);

  return (
    <div style={{ background: 'var(--bg-0)', color: 'var(--text-0)', minHeight: '100vh',
      fontFamily: 'var(--font-ui)' }}>
      <Header now={now} islandFilter={islandFilter} onIslandFilter={setIslandFilter}
        search={search} onSearch={setSearch} />
      <Ticker alerts={window.ALERTS} />

      <div style={{ padding: '24px 36px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between',
          alignItems: 'baseline', marginBottom: 22 }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--gold)', letterSpacing: '0.16em',
              fontFamily: 'var(--font-mono)', fontWeight: 600 }}>WIFI · COMMON AREAS</div>
            <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 6 }}>
              Good morning, John
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>
              Tuesday, April 28, 2026 · One outage needs attention
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button style={{
              padding: '8px 14px', fontSize: 12, background: 'var(--bg-2)',
              color: 'var(--text-1)', border: '1px solid var(--line)',
              borderRadius: 999, cursor: 'pointer',
            }}>Export</button>
            <button style={{
              padding: '8px 16px', fontSize: 12, fontWeight: 600,
              background: 'linear-gradient(135deg, var(--gold), var(--accent))',
              color: 'oklch(0.18 0.012 60)', border: 'none', borderRadius: 999,
              cursor: 'pointer',
              boxShadow: '0 0 calc(14px * var(--glow)) var(--accent-line)',
            }}>+ New Alert Rule</button>
          </div>
        </div>

        <IslandTiles filter={islandFilter} onFilter={setIslandFilter} />

        <div style={{ marginBottom: 18 }}>
          <HeroMap properties={filtered} onSelect={selectProp} selected={selected} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 16 }}>
          <GroupedProperties properties={filtered} onSelect={selectProp} selected={selected} />
          <HealthSidebar properties={filtered} alerts={window.ALERTS} />
          <AreaChart ssid={ssid} onSsidChange={setSsid} range={range} onRangeChange={setRange} />
          <Heatmap data={heat} />
        </div>
      </div>

      {drawerOpen && selectedProp && (
        <Drawer property={selectedProp} onClose={() => setDrawerOpen(false)} />
      )}

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}

window.Atrium = Atrium;
