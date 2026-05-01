// Variation 2 — Atrium
// Calmer hospitality-forward layout, large island map hero, refined cards, grouped by island

const { useState: useState2, useMemo: useMemo2, useEffect: useEffect2 } = React;

function AtriumSparkline({ data, color = 'var(--accent)', height = 36, width = 120 }) {
  const max = Math.max(...data), min = Math.min(...data);
  const range = Math.max(1, max - min);
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const id = `asl-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.55" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${height} ${points} ${width},${height}`} fill={`url(#${id})`} />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function AtriumHeader({ now, density, islandFilter, onIslandFilter }) {
  return (
    <div style={{
      padding: '20px 32px',
      borderBottom: '1px solid var(--line)',
      background: 'linear-gradient(180deg, oklch(0.22 0.018 80), oklch(0.18 0.012 60))',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <div style={{
          width: 38, height: 38, borderRadius: 12,
          background: 'linear-gradient(135deg, var(--gold), var(--accent))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--bg-0)', fontWeight: 700, fontSize: 18,
          boxShadow: '0 0 calc(20px * var(--glow)) oklch(0.80 0.12 85 / 0.35)',
        }}>◈</div>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>
            Atrium <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>Network</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', marginTop: 2 }}>
            COMMON AREA MONITOR · HST 08:56:20
          </div>
        </div>
      </div>
      <nav style={{ display: 'flex', gap: 28, fontSize: 13 }}>
        {['Overview','Properties','Networks','Alerts','Reports'].map((t,i)=>(
          <a key={t} style={{
            color: i===0 ? 'var(--text-0)' : 'var(--text-2)',
            textDecoration: 'none', position: 'relative', padding: '6px 0',
            fontWeight: i===0 ? 600 : 500, cursor: 'pointer',
          }}>
            {t}
            {i===0 && <span style={{
              position: 'absolute', left: 0, right: 0, bottom: -22, height: 2,
              background: 'linear-gradient(90deg, var(--gold), var(--accent))',
              boxShadow: '0 0 calc(8px * var(--glow)) var(--accent)',
            }} />}
          </a>
        ))}
      </nav>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <select value={islandFilter} onChange={(e)=>onIslandFilter(e.target.value)}
          style={{ background: 'transparent', color: 'var(--text-1)', border: '1px solid var(--line-strong)', borderRadius: 999, padding: '6px 14px', fontSize: 12, fontFamily: 'inherit' }}>
          <option value="all">All Islands</option>
          {window.ISLANDS.map(i=><option key={i} value={i}>{i}</option>)}
        </select>
        <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--gold))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--bg-0)' }}>JG</div>
      </div>
    </div>
  );
}

function AtriumTicker({ alerts }) {
  const items = [...alerts, ...alerts];
  return (
    <div style={{
      height: 32, display: 'flex', alignItems: 'center', overflow: 'hidden',
      background: 'oklch(0.18 0.012 60)', borderBottom: '1px solid var(--line)',
    }}>
      <div style={{ padding: '0 16px', fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', color: 'var(--accent)', borderRight: '1px solid var(--line)', height: '100%', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="pulse-dot bad" style={{ width: 6, height: 6 }} />
        FEED
      </div>
      <div style={{ display: 'flex', gap: 36, animation: 'tickerScroll 65s linear infinite', whiteSpace: 'nowrap', paddingLeft: 36 }}>
        {items.map((a, i) => (
          <span key={i} style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-2)', display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-3)' }}>{a.time}</span>
            <span style={{ color: a.severity==='critical'?'var(--bad)':a.severity==='warning'?'var(--warn)':'var(--accent)', fontWeight: 700, letterSpacing: '0.08em' }}>
              {a.severity.toUpperCase()}
            </span>
            <span style={{ color: 'var(--text-0)' }}>{a.property}</span>
            <span>{a.message}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function HeroMap({ properties, onSelect, selected }) {
  const islands = {
    'Kauai':     { x: 0.12, y: 0.32, r: 0.10 },
    'Oahu':      { x: 0.32, y: 0.40, r: 0.11 },
    'Maui':      { x: 0.58, y: 0.32, r: 0.13 },
    'Big Island':{ x: 0.82, y: 0.62, r: 0.16 },
  };
  const W = 900, H = 380;
  return (
    <div style={{ position: 'relative', height: 420, borderRadius: 20, overflow: 'hidden', border: '1px solid var(--line)',
      background: 'radial-gradient(ellipse at 20% 20%, oklch(0.78 0.13 195 / 0.10), transparent 55%), radial-gradient(ellipse at 80% 80%, oklch(0.80 0.12 85 / 0.06), transparent 60%), oklch(0.18 0.012 60)' }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <pattern id="atr-dots" width="18" height="18" patternUnits="userSpaceOnUse">
            <circle cx="9" cy="9" r="0.6" fill="oklch(0.45 0.012 60 / 0.35)" />
          </pattern>
          <radialGradient id="atr-island" cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor="oklch(0.40 0.025 80)" />
            <stop offset="100%" stopColor="oklch(0.24 0.015 80 / 0)" />
          </radialGradient>
        </defs>
        <rect width={W} height={H} fill="url(#atr-dots)" />
        {Object.entries(islands).map(([name, isl]) => (
          <g key={name}>
            <ellipse cx={isl.x*W} cy={isl.y*H} rx={isl.r*W} ry={isl.r*W*0.5}
              fill="url(#atr-island)" stroke="oklch(0.55 0.018 80 / 0.4)" strokeWidth="0.8" />
            <text x={isl.x*W} y={isl.y*H + isl.r*W*0.5 + 22} textAnchor="middle"
              fontSize="11" fontFamily="var(--font-mono)" letterSpacing="0.18em" fill="var(--text-3)">
              {name.toUpperCase()}
            </text>
          </g>
        ))}
        {/* concentric ranges around oahu */}
        {[40, 80, 130].map((r, i) => (
          <circle key={i} cx={islands.Oahu.x*W} cy={islands.Oahu.y*H} r={r} fill="none"
            stroke="var(--accent)" strokeWidth="0.5" strokeDasharray="2 5" opacity={0.25 - i*0.06} />
        ))}
        {properties.map(p => {
          const cx = p.lng*W, cy = p.lat*H;
          const c = p.status==='online'?'oklch(0.78 0.16 152)':p.status==='degraded'?'oklch(0.82 0.14 75)':'oklch(0.68 0.21 25)';
          const isSel = selected===p.id;
          return (
            <g key={p.id} style={{ cursor: 'pointer' }} onClick={()=>onSelect(p.id)}>
              {p.status!=='online' && (
                <circle cx={cx} cy={cy} r="20" fill="none" stroke={c} strokeWidth="1.2" opacity="0.6">
                  <animate attributeName="r" from="8" to="30" dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.7" to="0" dur="2s" repeatCount="indefinite" />
                </circle>
              )}
              <circle cx={cx} cy={cy} r={isSel?9:6} fill={c} style={{ filter: `drop-shadow(0 0 calc(8px * var(--glow)) ${c})` }} />
              <circle cx={cx} cy={cy} r={isSel?14:10} fill="none" stroke={c} strokeWidth="1" opacity="0.5" />
            </g>
          );
        })}
      </svg>
      {/* Map overlay stats */}
      <div style={{ position: 'absolute', top: 20, left: 24, right: 24, display: 'flex', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.14em', fontFamily: 'var(--font-mono)' }}>HAWAIIAN ISLANDS</div>
          <div style={{ fontSize: 26, fontWeight: 600, marginTop: 4, letterSpacing: '-0.02em' }}>15 properties · 36 networks</div>
          <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>798 connected devices · 14ms avg latency</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
          <span className="badge-glow bad">1 OUTAGE</span>
          <span className="badge-glow warn">1 DEGRADED</span>
          <span className="badge-glow ok">13 ONLINE</span>
        </div>
      </div>
      <div style={{ position: 'absolute', bottom: 20, left: 24, fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.14em', color: 'var(--text-3)' }}>
        21.31°N · 157.86°W
      </div>
    </div>
  );
}

function GroupedProperties({ properties, onSelect, selected }) {
  const grouped = window.ISLANDS.map(island => ({
    island, props: properties.filter(p => p.island === island)
  })).filter(g => g.props.length);

  return (
    <div className="card" style={{ gridColumn: 'span 8', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Properties by Island</h3>
          <div className="sub">{properties.length} TOTAL · GROUPED</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button style={{ padding: '6px 12px', fontSize: 11, fontWeight: 500, background: 'var(--accent-soft)', color: 'var(--accent)', border: '1px solid var(--accent-line)', borderRadius: 8, cursor: 'pointer' }}>All</button>
          <button style={{ padding: '6px 12px', fontSize: 11, fontWeight: 500, background: 'transparent', color: 'var(--text-2)', border: '1px solid var(--line)', borderRadius: 8, cursor: 'pointer' }}>Issues</button>
        </div>
      </div>
      {grouped.map(g => (
        <div key={g.island}>
          <div style={{ padding: '10px 22px', background: 'var(--bg-0)', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 4, height: 14, borderRadius: 2, background: 'linear-gradient(180deg, var(--gold), var(--accent))' }} />
              <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{g.island}</span>
              <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{g.props.length} properties</span>
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>
              {g.props.reduce((s,p)=>s+p.devices,0)} devices
            </div>
          </div>
          {g.props.map(p => {
            const sparkColor = p.status === 'online' ? 'oklch(0.78 0.13 195)' : p.status === 'degraded' ? 'oklch(0.82 0.14 75)' : 'oklch(0.68 0.21 25)';
            const isSel = selected === p.id;
            return (
              <div key={p.id} onClick={()=>onSelect(p.id)} style={{
                display: 'grid', gridTemplateColumns: '1.8fr 1fr 0.5fr 1.4fr 1fr',
                padding: 'calc(13px * var(--density)) 22px',
                alignItems: 'center', borderBottom: '1px solid var(--line)',
                cursor: 'pointer',
                background: isSel ? 'var(--accent-soft)' : 'transparent',
                borderLeft: isSel ? '3px solid var(--accent)' : '3px solid transparent',
                transition: 'background 0.15s',
              }} onMouseEnter={e => !isSel && (e.currentTarget.style.background = 'var(--bg-2)')}
                 onMouseLeave={e => !isSel && (e.currentTarget.style.background = 'transparent')}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span className={`pulse-dot ${p.status==='online'?'ok':p.status==='degraded'?'warn':'bad'}`} />
                  <div>
                    <div style={{ fontSize: 13.5, fontWeight: 500 }}>{p.name}</div>
                    <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{p.co}</div>
                  </div>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--text-2)' }}>
                  {p.networks} {p.networks === 1 ? 'network' : 'networks'}
                </div>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{p.devices}</div>
                <div><AtriumSparkline data={p.spark} color={sparkColor} /></div>
                <div style={{ textAlign: 'right' }}>
                  {p.status === 'online' && <span className="badge-glow ok">ONLINE</span>}
                  {p.status === 'degraded' && <span className="badge-glow warn">{p.offlineCount} DEGRADED</span>}
                  {p.status === 'offline' && <span className="badge-glow bad">{p.offlineCount} OFFLINE</span>}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function HealthSidebar({ properties, alerts }) {
  const total = properties.reduce((s,p)=>s+p.networks,0);
  const offline = properties.reduce((s,p)=>s+(p.offlineCount||0),0);
  const up = total - offline;
  const crit = alerts.filter(a=>a.severity==='critical');

  return (
    <div style={{ gridColumn: 'span 4', display: 'flex', flexDirection: 'column', gap: 16 }}>
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
          <button style={{ flex: 1, padding: '9px 14px', fontSize: 12, fontWeight: 600, background: 'var(--bad)', color: 'oklch(0.18 0.012 60)', border: 'none', borderRadius: 8, cursor: 'pointer', boxShadow: '0 0 calc(12px * var(--glow)) oklch(0.68 0.21 25 / 0.45)' }}>Acknowledge</button>
          <button style={{ flex: 1, padding: '9px 14px', fontSize: 12, fontWeight: 500, background: 'transparent', color: 'var(--text-1)', border: '1px solid var(--line-strong)', borderRadius: 8, cursor: 'pointer' }}>Dispatch</button>
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
          <KPI label="Offline" value={offline} sub="across 2 sites" color="var(--bad)" critical />
          <KPI label="Devices" value="781" sub="connected now" color="var(--accent)" />
          <KPI label="Latency" value="14ms" sub="avg, all hops" color="var(--gold)" mono />
        </div>
      </div>

      {/* Maintenance */}
      <div className="card" style={{ padding: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Scheduled Maintenance</div>
          <span className="badge-glow ok">CLEAR</span>
        </div>
        <div style={{ marginTop: 14, padding: '14px 16px', background: 'var(--bg-2)', borderRadius: 10, border: '1px dashed var(--line-strong)', textAlign: 'center' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: '0.14em', fontFamily: 'var(--font-mono)' }}>NEXT WINDOW</div>
          <div style={{ fontSize: 14, color: 'var(--text-1)', marginTop: 6 }}>None scheduled</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>Next quarterly check: May 15</div>
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

function AtriumChart({ ssid, onSsidChange, range, onRangeChange }) {
  const points = window.genTimeSeries(ssid==='all'?2:7, range==='7d'?168:24);
  const max = Math.max(...points.map(p=>p.total));
  return (
    <div className="card" style={{ gridColumn: 'span 8', padding: 0 }}>
      <div className="card-hd" style={{ borderBottom: '1px solid var(--line)' }}>
        <div>
          <h3>Connected Devices</h3>
          <div className="sub">REFRESH IN 2m 52s · {ssid==='all'?'ALL SSIDS':ssid.toUpperCase()}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select value={ssid} onChange={(e)=>onSsidChange(e.target.value)} style={{ background: 'var(--bg-2)', color: 'var(--text-1)', border: '1px solid var(--line)', borderRadius: 999, padding: '5px 12px', fontSize: 11.5, fontFamily: 'inherit' }}>
            <option value="all">All SSIDs</option>
            {window.SSIDS.map(s=><option key={s}>{s}</option>)}
          </select>
          <div style={{ display: 'flex', background: 'var(--bg-2)', borderRadius: 999, padding: 2, border: '1px solid var(--line)' }}>
            {['1d','7d'].map(r=>(
              <button key={r} onClick={()=>onRangeChange(r)} style={{ padding: '4px 12px', fontSize: 11, fontWeight: 600, background: range===r?'linear-gradient(135deg, var(--gold), var(--accent))':'transparent', color: range===r?'oklch(0.18 0.012 60)':'var(--text-2)', border: 'none', borderRadius: 999, cursor: 'pointer' }}>{r.toUpperCase()}</button>
            ))}
          </div>
        </div>
      </div>
      <div style={{ padding: '20px 22px 16px', position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 200 }}>
          {points.map((p,i)=>{
            const lh = (p.lobby/max)*200, ph = (p.pool/max)*200;
            return (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', minWidth: 0 }}>
                <div style={{ height: ph, background: 'linear-gradient(180deg, var(--gold), oklch(0.65 0.13 70))', borderRadius: '2px 2px 0 0' }} />
                <div style={{ height: lh, background: 'linear-gradient(180deg, var(--accent), oklch(0.55 0.13 200))' }} />
              </div>
            );
          })}
        </div>
        <div style={{ position: 'absolute', inset: '20px 22px 16px', pointerEvents: 'none' }}>
          {[0.25,0.5,0.75].map(p=>(
            <div key={p} style={{ position: 'absolute', left: 0, right: 0, top: `${p*200}px`, borderTop: '1px dashed var(--line)' }} />
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-3)' }}>
          {['04/22','04/23','04/24','04/25','04/26','04/27','04/28'].map(d=><span key={d}>{d}</span>)}
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 14, fontSize: 11.5 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 10, height: 10, background: 'var(--accent)', borderRadius: 2, boxShadow: '0 0 calc(6px * var(--glow)) var(--accent)' }} /> Lobby / Front Desk
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 10, height: 10, background: 'var(--gold)', borderRadius: 2, boxShadow: '0 0 calc(6px * var(--glow)) var(--gold)' }} /> Pool / Bar
          </span>
        </div>
      </div>
    </div>
  );
}

function AtriumHeatmap({ data }) {
  const days = ['MON','TUE','WED','THU','FRI','SAT','SUN'];
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
            {days.map(d=><div key={d} style={{ height: 20, fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', letterSpacing: '0.1em', display: 'flex', alignItems: 'center' }}>{d}</div>)}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-3)', marginBottom: 4 }}>
              {[0,6,12,18,23].map(h=><span key={h}>{String(h).padStart(2,'0')}h</span>)}
            </div>
            {data.map((row,i)=>(
              <div key={i} style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: 2, marginBottom: 2 }}>
                {row.map((v,j)=>{
                  const hue = 195 - v*110;
                  const c = `oklch(${0.30 + v*0.45} ${0.05 + v*0.13} ${hue})`;
                  return <div key={j} style={{ height: 20, background: c, borderRadius: 3, boxShadow: v>0.7?`0 0 calc(4px * var(--glow)) ${c}`:'none' }} />;
                })}
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 14, padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>PEAK</div>
          <div style={{ fontSize: 13, color: 'var(--text-1)', fontWeight: 500, marginTop: 2 }}>Friday 19:00 · 412 devices</div>
        </div>
      </div>
    </div>
  );
}

function Atrium() {
  const [now, setNow] = useState2({ h: '08', m: '56', s: '20' });
  const [islandFilter, setIslandFilter] = useState2('all');
  const [selected, setSelected] = useState2(null);
  const [ssid, setSsid] = useState2('all');
  const [range, setRange] = useState2('7d');

  useEffect2(()=>{
    const id = setInterval(()=>{
      const d = new Date();
      const pad = n=>String(n).padStart(2,'0');
      setNow({ h: pad(d.getHours()), m: pad(d.getMinutes()), s: pad(d.getSeconds()) });
    }, 1000);
    return ()=>clearInterval(id);
  }, []);

  const filtered = useMemo2(()=>{
    if (islandFilter==='all') return window.PROPERTIES;
    return window.PROPERTIES.filter(p=>p.island===islandFilter);
  }, [islandFilter]);

  const heat = useMemo2(()=>window.genHeatmap(11), []);

  return (
    <div className="dash">
      <AtriumHeader now={now} islandFilter={islandFilter} onIslandFilter={setIslandFilter} />
      <AtriumTicker alerts={window.ALERTS} />
      <div style={{ padding: '24px 32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 18 }}>
          <div>
            <div style={{ fontSize: 13, color: 'var(--gold)', letterSpacing: '0.16em', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>WIFI · COMMON AREAS</div>
            <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 6 }}>Good morning, John</div>
            <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>Tuesday, April 28, 2026 · One outage needs attention</div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button style={{ padding: '8px 14px', fontSize: 12, background: 'var(--bg-2)', color: 'var(--text-1)', border: '1px solid var(--line)', borderRadius: 999, cursor: 'pointer' }}>Export</button>
            <button style={{ padding: '8px 16px', fontSize: 12, fontWeight: 600, background: 'linear-gradient(135deg, var(--gold), var(--accent))', color: 'oklch(0.18 0.012 60)', border: 'none', borderRadius: 999, cursor: 'pointer', boxShadow: '0 0 calc(14px * var(--glow)) var(--accent-line)' }}>+ New Alert Rule</button>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <HeroMap properties={filtered} onSelect={setSelected} selected={selected} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 16 }}>
          <GroupedProperties properties={filtered} onSelect={setSelected} selected={selected} />
          <HealthSidebar properties={filtered} alerts={window.ALERTS} />
          <AtriumChart ssid={ssid} onSsidChange={setSsid} range={range} onRangeChange={setRange} />
          <AtriumHeatmap data={heat} />
        </div>
      </div>
    </div>
  );
}

window.Atrium = Atrium;
