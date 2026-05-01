// Variation 1 — Operations Center
// Alert-first dense layout, ticker, heatmap, sparklines, integrated trend chart

const { useState, useMemo, useEffect } = React;

// ---------- small primitives ----------
function Sparkline({ data, color = 'var(--accent)', height = 28, width = 96 }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = Math.max(1, max - min);
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const area = `0,${height} ${points} ${width},${height}`;
  const lastX = width;
  const lastY = height - ((data[data.length - 1] - min) / range) * (height - 4) - 2;
  const id = `sl-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.45" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${id})`} />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r="2.2" fill={color} />
    </svg>
  );
}

function RadialGauge({ value, total, size = 144 }) {
  const pct = value / total;
  const r = size / 2 - 10;
  const c = 2 * Math.PI * r;
  const dash = c * pct;
  const cx = size / 2;
  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="gaugeG" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="oklch(0.78 0.16 152)" />
          <stop offset="100%" stopColor="oklch(0.78 0.13 195)" />
        </linearGradient>
        <filter id="gaugeBlur" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
      </defs>
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--bg-3)" strokeWidth="8" />
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="url(#gaugeG)" strokeWidth="8"
        strokeDasharray={`${dash} ${c}`} strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cx})`}
        filter="url(#gaugeBlur)"
        opacity={0.5}
      />
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="url(#gaugeG)" strokeWidth="6"
        strokeDasharray={`${dash} ${c}`} strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cx})`}
      />
      <text x={cx} y={cx - 2} textAnchor="middle" fontSize="34" fontWeight="700"
        fill="var(--text-0)" fontFamily="var(--font-mono)">{value}</text>
      <text x={cx} y={cx + 18} textAnchor="middle" fontSize="10" letterSpacing="0.15em"
        fill="var(--text-3)" fontFamily="var(--font-mono)">OF {total}</text>
    </svg>
  );
}

// ---------- Ticker ----------
function Ticker({ alerts }) {
  const items = [...alerts, ...alerts];
  return (
    <div className="ticker">
      <div className="ticker-track">
        {items.map((a, i) => (
          <span key={i} className="ticker-item">
            <span className={`sev ${a.severity === 'critical' ? 'crit' : a.severity}`}>
              {a.severity === 'critical' ? '◆ CRITICAL' : a.severity === 'warning' ? '▲ WARN' : '● INFO'}
            </span>
            <span className="sep">/</span>
            <span style={{ color: 'var(--text-0)' }}>{a.property}</span>
            <span className="sep">·</span>
            <span>{a.message}</span>
            <span className="sep" style={{ marginLeft: 8 }}>{a.age} ago</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ---------- Top bar ----------
function TopBar({ now, density, onIslandFilter, islandFilter }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 28px', borderBottom: '1px solid var(--line)',
      background: 'linear-gradient(180deg, var(--bg-1), var(--bg-0))',
      position: 'relative', zIndex: 2,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: 'conic-gradient(from 220deg, var(--accent), var(--gold), var(--accent))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 calc(14px * var(--glow)) var(--accent-line)',
        }}>
          <div style={{
            width: 22, height: 22, borderRadius: 6, background: 'var(--bg-0)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: 'var(--accent)',
          }}>◊</div>
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.04em' }}>COMMON AREA NETWORK MONITOR</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', marginTop: 2 }}>
            v3.2 · 15 PROPERTIES · 36 NETWORKS · 798 DEVICES
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4, marginLeft: 28 }}>
          {['Overview', 'Properties', 'Alerts', 'Maps', 'Reports'].map((t, i) => (
            <button key={t} style={{
              padding: '7px 14px', fontSize: 12, fontWeight: 500, letterSpacing: '0.02em',
              border: '1px solid ' + (i === 0 ? 'var(--accent-line)' : 'transparent'),
              background: i === 0 ? 'var(--accent-soft)' : 'transparent',
              color: i === 0 ? 'var(--accent)' : 'var(--text-2)',
              borderRadius: 8, cursor: 'pointer',
            }}>{t}</button>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <select value={islandFilter} onChange={(e) => onIslandFilter(e.target.value)}
          style={{
            background: 'var(--bg-2)', color: 'var(--text-0)', border: '1px solid var(--line)',
            borderRadius: 8, padding: '7px 12px', fontSize: 12, fontFamily: 'inherit',
          }}>
          <option value="all">All Islands</option>
          {window.ISLANDS.map(i => <option key={i} value={i}>{i}</option>)}
        </select>
        <div style={{ textAlign: 'right' }}>
          <div className="mono" style={{ fontSize: 18, fontWeight: 600, letterSpacing: '0.05em', color: 'var(--accent)' }}>
            {now.h}<span style={{ color: 'var(--text-3)' }}>:</span>{now.m}<span style={{ color: 'var(--text-3)' }}>:</span>{now.s}
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
            HST · TUE APR 28 2026
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', background: 'var(--bg-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
          <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--gold))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--bg-0)' }}>JG</div>
          <div style={{ fontSize: 12, color: 'var(--text-1)' }}>jgarces</div>
        </div>
      </div>
    </div>
  );
}

// ---------- Hero outage card ----------
function OutageHero({ alerts }) {
  const crit = alerts.filter(a => a.severity === 'critical');
  const top = crit[0];
  return (
    <div className="card" style={{
      gridColumn: 'span 5',
      padding: 22,
      background: 'linear-gradient(135deg, oklch(0.68 0.21 25 / 0.12), var(--bg-1) 60%)',
      borderColor: 'oklch(0.68 0.21 25 / 0.35)',
      boxShadow: '0 0 calc(40px * var(--glow)) oklch(0.68 0.21 25 / calc(0.15 * var(--glow))), inset 0 1px 0 oklch(0.68 0.21 25 / 0.20)',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* corner glyph */}
      <div style={{ position: 'absolute', right: -40, top: -40, width: 220, height: 220, borderRadius: '50%',
        background: 'radial-gradient(circle, oklch(0.68 0.21 25 / 0.18), transparent 70%)' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="pulse-dot bad" style={{ width: 10, height: 10 }} />
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', color: 'var(--bad)' }}>ACTIVE OUTAGE</span>
        </div>
        <span className="badge-glow bad">2 CRITICAL · {alerts.filter(a => a.severity==='warning').length} WARN</span>
      </div>
      <div style={{ marginTop: 18, fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
        {top.property}
      </div>
      <div style={{ marginTop: 6, fontSize: 14, color: 'var(--text-2)' }}>
        {top.network}
      </div>
      <div style={{
        marginTop: 18, padding: '14px 16px', background: 'oklch(0.18 0.012 60 / 0.6)',
        border: '1px solid var(--line)', borderRadius: 12,
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16,
      }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.12em', marginBottom: 4 }}>TYPE</div>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-0)' }}>Device Outage</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.12em', marginBottom: 4 }}>STARTED</div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-0)' }}>08:42 HST</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.12em', marginBottom: 4 }}>DURATION</div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 500, color: 'var(--bad)' }}>00:14:32</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.12em', marginBottom: 4 }}>IMPACT</div>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-0)' }}>~24 guests</div>
        </div>
      </div>
      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: 'var(--text-2)' }}>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>DEVICE</span>
        <span style={{ color: 'var(--text-1)' }}>{top.device}</span>
      </div>
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button style={{
          padding: '8px 14px', fontSize: 12, fontWeight: 600,
          background: 'var(--bad)', color: 'oklch(0.18 0.012 60)', border: 'none', borderRadius: 8, cursor: 'pointer',
          boxShadow: '0 0 calc(12px * var(--glow)) oklch(0.68 0.21 25 / 0.45)',
        }}>Acknowledge</button>
        <button style={{
          padding: '8px 14px', fontSize: 12, fontWeight: 500,
          background: 'transparent', color: 'var(--text-1)', border: '1px solid var(--line-strong)', borderRadius: 8, cursor: 'pointer',
        }}>Dispatch tech</button>
        <button style={{
          padding: '8px 14px', fontSize: 12, fontWeight: 500,
          background: 'transparent', color: 'var(--text-2)', border: '1px solid var(--line)', borderRadius: 8, cursor: 'pointer',
        }}>View timeline →</button>
      </div>
    </div>
  );
}

// ---------- Network Health card ----------
function NetworkHealth({ properties }) {
  const total = properties.reduce((s, p) => s + p.networks, 0);
  const offline = properties.reduce((s, p) => s + (p.offlineCount || 0), 0);
  const up = total - offline;
  return (
    <div className="card" style={{ gridColumn: 'span 4', padding: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', letterSpacing: '0.02em' }}>Network Health</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', marginTop: 2 }}>
            POLLED 12s AGO
          </div>
        </div>
        <span className="badge-glow accent">98.4% UPTIME 7D</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginTop: 16 }}>
        <RadialGauge value={up} total={total} size={140} />
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <Stat label="Up" value={up} color="var(--ok)" />
          <Stat label="Down" value={offline} color="var(--bad)" critical={offline > 0} />
          <Stat label="Devices online" value="781" color="var(--accent)" />
          <Stat label="Avg latency" value="14ms" color="var(--gold)" mono />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color, critical, mono }) {
  return (
    <div style={{
      padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 10,
      border: critical ? '1px solid oklch(0.68 0.21 25 / 0.45)' : '1px solid var(--line)',
      boxShadow: critical ? '0 0 calc(10px * var(--glow)) oklch(0.68 0.21 25 / calc(0.30 * var(--glow)))' : 'none',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.12em', marginBottom: 3 }}>{label.toUpperCase()}</div>
      <div className={mono ? 'mono' : ''} style={{ fontSize: 22, fontWeight: 700, color, letterSpacing: '-0.01em' }}>{value}</div>
    </div>
  );
}

// ---------- Map of islands with pins ----------
function IslandMap({ properties, onSelect, selected }) {
  // Abstract dot-grid Hawaiian island visualization (not a traced coastline)
  const islands = {
    'Kauai':     { x: 0.16, y: 0.32, r: 0.12 },
    'Oahu':      { x: 0.40, y: 0.42, r: 0.13 },
    'Maui':      { x: 0.65, y: 0.30, r: 0.15 },
    'Big Island':{ x: 0.85, y: 0.62, r: 0.18 },
  };
  const W = 560, H = 320;

  // Draw an island as a stippled cluster
  const stippleId = (key) => `dots-${key}`;

  return (
    <div className="card" style={{ gridColumn: 'span 7', padding: 0, overflow: 'hidden', position: 'relative' }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Island Network Map</h3>
          <div className="sub">15 PROPERTIES · LIVE</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[{c:'var(--ok)',l:'Online',n:13},{c:'var(--warn)',l:'Degraded',n:1},{c:'var(--bad)',l:'Offline',n:1}].map(x=>(
            <div key={x.l} style={{ display:'flex', alignItems:'center', gap:6, fontSize:11, color:'var(--text-2)', padding:'4px 10px', background:'var(--bg-2)', borderRadius:999, border:'1px solid var(--line)' }}>
              <span className={`pulse-dot ${x.l==='Online'?'ok':x.l==='Degraded'?'warn':'bad'}`} style={{width:6,height:6}}/>
              {x.l} <span className="mono" style={{color:'var(--text-3)'}}>{x.n}</span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ position: 'relative', height: 320, background: 'radial-gradient(ellipse at 30% 30%, oklch(0.78 0.13 195 / 0.06), transparent 60%), var(--bg-1)' }}>
        {/* dot grid bg */}
        <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <pattern id="ocean-dots" width="14" height="14" patternUnits="userSpaceOnUse">
              <circle cx="7" cy="7" r="0.7" fill="oklch(0.40 0.012 60 / 0.5)" />
            </pattern>
            <radialGradient id="island-grad" cx="50%" cy="40%" r="60%">
              <stop offset="0%" stopColor="oklch(0.36 0.020 80)" />
              <stop offset="80%" stopColor="oklch(0.26 0.018 80)" />
              <stop offset="100%" stopColor="oklch(0.22 0.015 80 / 0)" />
            </radialGradient>
          </defs>
          <rect width={W} height={H} fill="url(#ocean-dots)" />

          {/* islands */}
          {Object.entries(islands).map(([name, isl]) => (
            <g key={name}>
              <ellipse cx={isl.x * W} cy={isl.y * H} rx={isl.r * W} ry={isl.r * W * 0.55}
                fill="url(#island-grad)" stroke="oklch(0.50 0.015 80 / 0.5)" strokeWidth="0.7" />
              <text x={isl.x * W} y={isl.y * H + isl.r * W * 0.55 + 16}
                textAnchor="middle" fontSize="10" fontFamily="var(--font-mono)" letterSpacing="0.15em"
                fill="var(--text-3)">{name.toUpperCase()}</text>
            </g>
          ))}

          {/* connector arcs between islands (decorative) */}
          {(() => {
            const order = ['Kauai','Oahu','Maui','Big Island'];
            const lines = [];
            for (let i=0;i<order.length-1;i++) {
              const a = islands[order[i]], b = islands[order[i+1]];
              lines.push(
                <path key={i} d={`M ${a.x*W} ${a.y*H} Q ${(a.x+b.x)/2*W} ${Math.min(a.y,b.y)*H - 30}, ${b.x*W} ${b.y*H}`}
                  fill="none" stroke="var(--accent)" strokeWidth="0.8" strokeDasharray="2 4" opacity="0.4" />
              );
            }
            return lines;
          })()}

          {/* property pins */}
          {properties.map((p) => {
            const cx = p.lng * W;
            const cy = p.lat * H;
            const color = p.status === 'online' ? 'oklch(0.78 0.16 152)' : p.status === 'degraded' ? 'oklch(0.82 0.14 75)' : 'oklch(0.68 0.21 25)';
            const isSel = selected === p.id;
            return (
              <g key={p.id} style={{ cursor: 'pointer' }} onClick={() => onSelect(p.id)}>
                {p.status !== 'online' && (
                  <circle cx={cx} cy={cy} r="14" fill="none" stroke={color} strokeWidth="1" opacity="0.5">
                    <animate attributeName="r" from="6" to="22" dur="1.8s" repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.7" to="0" dur="1.8s" repeatCount="indefinite" />
                  </circle>
                )}
                <circle cx={cx} cy={cy} r={isSel ? 7 : 5} fill={color}
                  style={{ filter: `drop-shadow(0 0 calc(6px * var(--glow)) ${color})` }} />
                <circle cx={cx} cy={cy} r={isSel ? 11 : 8} fill="none" stroke={color} strokeWidth="1" opacity="0.5" />
              </g>
            );
          })}
        </svg>

        {/* compass / scale */}
        <div style={{
          position: 'absolute', bottom: 14, left: 18, fontFamily: 'var(--font-mono)', fontSize: 10,
          color: 'var(--text-3)', letterSpacing: '0.12em', display: 'flex', alignItems: 'center', gap: 18,
        }}>
          <span>21.31°N · 157.86°W</span>
          <span>N ↑</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ display: 'inline-block', width: 24, height: 1, background: 'var(--text-3)' }} />
            50 mi
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------- Property table with sparklines ----------
function PropertyTable({ properties, onSelect, selected }) {
  return (
    <div className="card" style={{ gridColumn: 'span 7', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Property Status</h3>
          <div className="sub">{properties.length} PROPERTIES · 7-DAY TREND</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button style={btnGhost(true)}>All</button>
          <button style={btnGhost(false)}>Issues</button>
          <button style={btnGhost(false)}>Online</button>
        </div>
      </div>
      <div style={{ overflow: 'hidden' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1.6fr 0.9fr 0.6fr 1.2fr 0.7fr 1fr',
          padding: '10px 18px', fontSize: 10, color: 'var(--text-3)',
          letterSpacing: '0.14em', borderBottom: '1px solid var(--line)',
          fontFamily: 'var(--font-mono)',
        }}>
          <div>PROPERTY</div>
          <div>CENTRAL OFFICE</div>
          <div>NETS</div>
          <div>7-DAY DEVICES</div>
          <div>NOW</div>
          <div style={{ textAlign: 'right' }}>STATE</div>
        </div>
        {properties.map((p) => {
          const sparkColor = p.status === 'online' ? 'oklch(0.78 0.13 195)' : p.status === 'degraded' ? 'oklch(0.82 0.14 75)' : 'oklch(0.68 0.21 25)';
          const isSel = selected === p.id;
          return (
            <div key={p.id} onClick={() => onSelect(p.id)} style={{
              display: 'grid', gridTemplateColumns: '1.6fr 0.9fr 0.6fr 1.2fr 0.7fr 1fr',
              padding: 'calc(11px * var(--density)) 18px',
              alignItems: 'center', borderBottom: '1px solid var(--line)',
              background: isSel ? 'var(--accent-soft)' : 'transparent',
              cursor: 'pointer', transition: 'background 0.15s',
              borderLeft: isSel ? '2px solid var(--accent)' : '2px solid transparent',
            }} onMouseEnter={e => !isSel && (e.currentTarget.style.background = 'var(--bg-2)')}
               onMouseLeave={e => !isSel && (e.currentTarget.style.background = 'transparent')}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className={`pulse-dot ${p.status === 'online' ? 'ok' : p.status === 'degraded' ? 'warn' : 'bad'}`} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{p.island}</div>
                </div>
              </div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{p.co}</div>
              <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{p.networks}</div>
              <div><Sparkline data={p.spark} color={sparkColor} /></div>
              <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>{p.devices}</div>
              <div style={{ textAlign: 'right' }}>
                {p.status === 'online' && <span className="badge-glow ok">ALL ONLINE</span>}
                {p.status === 'degraded' && <span className="badge-glow warn">{p.offlineCount} DEGRADED</span>}
                {p.status === 'offline' && <span className="badge-glow bad">{p.offlineCount} OFFLINE</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function btnGhost(active) {
  return {
    padding: '6px 12px', fontSize: 11, fontWeight: 500,
    background: active ? 'var(--accent-soft)' : 'transparent',
    color: active ? 'var(--accent)' : 'var(--text-2)',
    border: '1px solid ' + (active ? 'var(--accent-line)' : 'var(--line)'),
    borderRadius: 8, cursor: 'pointer',
  };
}

// ---------- Heatmap ----------
function Heatmap({ data }) {
  const days = ['MON','TUE','WED','THU','FRI','SAT','SUN'];
  return (
    <div className="card" style={{ gridColumn: 'span 5', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Activity Heatmap</h3>
          <div className="sub">CONNECTIONS BY HOUR · 7D</div>
        </div>
        <span className="badge-glow accent">PEAK 18:00–22:00</span>
      </div>
      <div style={{ padding: '14px 18px 18px' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, paddingTop: 16 }}>
            {days.map(d => <div key={d} style={{ height: 18, fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', letterSpacing: '0.12em', display: 'flex', alignItems: 'center' }}>{d}</div>)}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: 4 }}>
              {[0,4,8,12,16,20,23].map(h => <span key={h}>{String(h).padStart(2,'0')}</span>)}
            </div>
            {data.map((row, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: 3, marginBottom: 3 }}>
                {row.map((v, j) => {
                  // teal-to-coral scale
                  const hue = 195 - v * 110;
                  const c = `oklch(${0.30 + v * 0.45} ${0.05 + v * 0.13} ${hue})`;
                  return <div key={j} style={{
                    height: 18,
                    background: c,
                    borderRadius: 3,
                    boxShadow: v > 0.7 ? `0 0 calc(4px * var(--glow)) ${c}` : 'none',
                  }} title={`${v.toFixed(2)}`} />;
                })}
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', letterSpacing: '0.1em' }}>
          <span>LOW</span>
          <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'linear-gradient(90deg, oklch(0.30 0.05 195), oklch(0.55 0.13 145), oklch(0.65 0.18 85), oklch(0.68 0.21 25))' }} />
          <span>HIGH</span>
        </div>
      </div>
    </div>
  );
}

// ---------- Trend chart (stacked bar, like screenshot 2) ----------
function TrendChart({ ssid, onSsidChange, range, onRangeChange }) {
  const points = window.genTimeSeries(ssid === 'all' ? 1 : 5, range === '7d' ? 168 : 24, 6, 14, 14, 28);
  const max = Math.max(...points.map(p => p.total));
  return (
    <div className="card" style={{ gridColumn: 'span 12', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Connected Devices Over Time</h3>
          <div className="sub">NEXT UPDATE: 2m 52s · {ssid === 'all' ? 'ALL SSIDS' : ssid.toUpperCase()}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select value={ssid} onChange={(e) => onSsidChange(e.target.value)} style={{
            background: 'var(--bg-2)', color: 'var(--text-1)', border: '1px solid var(--line)',
            borderRadius: 8, padding: '6px 10px', fontSize: 11.5, fontFamily: 'inherit',
          }}>
            <option value="all">All SSIDs</option>
            {window.SSIDS.map(s => <option key={s}>{s}</option>)}
          </select>
          <div style={{ display: 'flex', background: 'var(--bg-2)', borderRadius: 8, padding: 2, border: '1px solid var(--line)' }}>
            {['1d','7d'].map(r => (
              <button key={r} onClick={() => onRangeChange(r)} style={{
                padding: '5px 12px', fontSize: 11, fontWeight: 600, letterSpacing: '0.05em',
                background: range === r ? 'var(--accent)' : 'transparent',
                color: range === r ? 'oklch(0.18 0.012 60)' : 'var(--text-2)',
                border: 'none', borderRadius: 6, cursor: 'pointer',
              }}>{r.toUpperCase()}</button>
            ))}
          </div>
        </div>
      </div>
      <div style={{ padding: '18px 22px 14px', position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1.5, height: 180 }}>
          {points.map((p, i) => {
            const lobbyH = (p.lobby / max) * 180;
            const poolH = (p.pool / max) * 180;
            return (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', minWidth: 0 }}>
                <div style={{
                  height: poolH, background: 'linear-gradient(180deg, var(--gold), oklch(0.70 0.13 70))',
                  borderRadius: '2px 2px 0 0',
                }} />
                <div style={{
                  height: lobbyH, background: 'linear-gradient(180deg, var(--accent), oklch(0.62 0.13 200))',
                }} />
              </div>
            );
          })}
        </div>
        {/* gridlines */}
        <div style={{ position: 'absolute', inset: '18px 22px 14px', pointerEvents: 'none' }}>
          {[0.25, 0.5, 0.75].map(p => (
            <div key={p} style={{ position: 'absolute', left: 0, right: 0, top: `${p * 180}px`, borderTop: '1px dashed var(--line)' }} />
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.1em' }}>
          <span>04/21</span><span>04/22</span><span>04/23</span><span>04/24</span><span>04/25</span><span>04/26</span><span>04/27</span><span>04/28</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 12, fontSize: 11.5 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--text-1)' }}>
            <span style={{ width: 10, height: 10, background: 'var(--accent)', borderRadius: 2, boxShadow: '0 0 calc(6px * var(--glow)) var(--accent)' }} />
            Lobby / Front Desk
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--text-1)' }}>
            <span style={{ width: 10, height: 10, background: 'var(--gold)', borderRadius: 2, boxShadow: '0 0 calc(6px * var(--glow)) var(--gold)' }} />
            Pool / Front Desk / Bar
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------- Alerts feed ----------
function AlertsFeed({ alerts }) {
  return (
    <div className="card" style={{ gridColumn: 'span 3', padding: 0, alignSelf: 'stretch' }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Live Alerts</h3>
          <div className="sub">{alerts.length} IN LAST 4H</div>
        </div>
        <span className="badge-glow accent">AUTO ▲</span>
      </div>
      <div style={{ maxHeight: 540, overflow: 'auto' }}>
        {alerts.map((a) => (
          <div key={a.id} style={{
            padding: '14px 18px',
            borderBottom: '1px solid var(--line)',
            display: 'flex', flexDirection: 'column', gap: 4,
            cursor: 'pointer',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className={`badge-glow ${a.severity === 'critical' ? 'bad' : a.severity === 'warning' ? 'warn' : 'ok'}`}>
                {a.severity === 'critical' ? 'CRIT' : a.severity === 'warning' ? 'WARN' : 'INFO'}
              </span>
              <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{a.time}</span>
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-0)', fontWeight: 500 }}>{a.property}</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.4 }}>{a.message}</div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{a.network}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- The variation ----------
function OperationsCenter() {
  const [now, setNow] = useState({ h: '08', m: '56', s: '20' });
  const [islandFilter, setIslandFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [ssid, setSsid] = useState('all');
  const [range, setRange] = useState('7d');

  useEffect(() => {
    const id = setInterval(() => {
      const d = new Date();
      // shift to HST display (just synthetic)
      const pad = (n) => String(n).padStart(2, '0');
      setNow({ h: pad(d.getHours()), m: pad(d.getMinutes()), s: pad(d.getSeconds()) });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const filteredProps = useMemo(() => {
    if (islandFilter === 'all') return window.PROPERTIES;
    return window.PROPERTIES.filter(p => p.island === islandFilter);
  }, [islandFilter]);

  const heat = useMemo(() => window.genHeatmap(7), []);

  return (
    <div className="dash grid-bg">
      <TopBar now={now} onIslandFilter={setIslandFilter} islandFilter={islandFilter} />
      <Ticker alerts={window.ALERTS} />
      <div style={{ padding: 22 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em' }}>WiFi Common Area Overview</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>
              Real-time monitoring across {filteredProps.length} {islandFilter === 'all' ? 'properties' : `${islandFilter} properties`}
            </div>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.1em' }}>
            LAST SYNC <span style={{ color: 'var(--accent)' }}>● </span>12s
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 16 }}>
          <OutageHero alerts={window.ALERTS} />
          <NetworkHealth properties={filteredProps} />
          <AlertsFeed alerts={window.ALERTS} />
          <IslandMap properties={filteredProps} onSelect={setSelected} selected={selected} />
          <Heatmap data={heat} />
          <PropertyTable properties={filteredProps} onSelect={setSelected} selected={selected} />
          <TrendChart ssid={ssid} onSsidChange={setSsid} range={range} onRangeChange={setRange} />
        </div>
      </div>
    </div>
  );
}

window.OperationsCenter = OperationsCenter;
