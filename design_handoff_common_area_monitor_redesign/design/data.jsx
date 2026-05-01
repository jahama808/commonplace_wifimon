// Shared data for both dashboard variations
// Hawaii hospitality property network monitor

const ISLANDS = ['Oahu', 'Maui', 'Big Island', 'Kauai'];

const PROPERTIES = [
  { id: 'aks', name: 'Aston Kaanapali Shores', co: 'LHNAHICO', island: 'Maui', networks: 2, status: 'online', devices: 47, lat: 0.62, lng: 0.18 },
  { id: 'bvk', name: 'Beach Villas at Koolina', co: 'PKAPHIXA', island: 'Oahu', networks: 4, status: 'online', devices: 89, lat: 0.45, lng: 0.32 },
  { id: 'cap', name: 'Capitol Place', co: 'HNLLHIMN', island: 'Oahu', networks: 3, status: 'online', devices: 64, lat: 0.51, lng: 0.42 },
  { id: 'hbr', name: 'Hanalei Bay Resort', co: 'KLOAHICO', island: 'Kauai', networks: 1, status: 'online', devices: 23, lat: 0.22, lng: 0.12 },
  { id: 'imp', name: 'Imperial Plaza', co: 'HNLLHIXA', island: 'Oahu', networks: 1, status: 'online', devices: 31, lat: 0.55, lng: 0.45 },
  { id: 'kol', name: 'Koola Lai', co: '—', island: 'Oahu', networks: 2, status: 'online', devices: 38, lat: 0.48, lng: 0.39 },
  { id: 'khl', name: 'Koko Head Labs', co: 'KOKOHICO', island: 'Oahu', networks: 1, status: 'online', devices: 19, lat: 0.58, lng: 0.50 },
  { id: 'owk', name: 'Owaka Street', co: 'WLKUHIMN', island: 'Maui', networks: 1, status: 'online', devices: 12, lat: 0.65, lng: 0.21 },
  { id: 'prk', name: 'Park Lane', co: 'HNLLHIXA', island: 'Oahu', networks: 13, status: 'offline', devices: 218, lat: 0.50, lng: 0.41, offlineCount: 13 },
  { id: 'pak', name: 'The Pakalana', co: 'HNLLHIMN', island: 'Oahu', networks: 1, status: 'degraded', devices: 8, lat: 0.53, lng: 0.44, offlineCount: 1 },
  { id: 'mok', name: 'Mokulele Heights', co: 'KAHUHIMN', island: 'Maui', networks: 2, status: 'online', devices: 41, lat: 0.68, lng: 0.25 },
  { id: 'kon', name: 'Kona Sands', co: 'KAILHICO', island: 'Big Island', networks: 3, status: 'online', devices: 56, lat: 0.82, lng: 0.55 },
  { id: 'wai', name: 'Waikoloa Vista', co: 'WIKLHICO', island: 'Big Island', networks: 2, status: 'online', devices: 33, lat: 0.85, lng: 0.50 },
  { id: 'lhi', name: 'Lahaina Pointe', co: 'LHNAHIMN', island: 'Maui', networks: 1, status: 'online', devices: 18, lat: 0.61, lng: 0.16 },
  { id: 'pri', name: 'Princeville Cliffs', co: 'PRVLHICO', island: 'Kauai', networks: 2, status: 'online', devices: 27, lat: 0.20, lng: 0.10 },
];

// Generate a 7-day connected-devices time series, dual-network stacked
function genTimeSeries(seed = 1, points = 168, baseLow = 6, baseHigh = 14, peakLow = 14, peakHigh = 28) {
  const series = [];
  let s = seed;
  const rand = () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
  for (let i = 0; i < points; i++) {
    const hour = i % 24;
    // peak in evening (16-22)
    const peak = hour >= 16 && hour <= 22 ? 1 : hour >= 9 && hour <= 15 ? 0.6 : 0.25;
    const dayBoost = Math.floor(i / 24) === 1 ? 1.4 : 1.0; // a peak day
    const lobby = Math.round((baseLow + rand() * (baseHigh - baseLow)) * (1 + peak * 0.6) * dayBoost);
    const pool = Math.round((peakLow + rand() * (peakHigh - peakLow)) * peak * dayBoost * 0.45);
    series.push({ lobby, pool, total: lobby + pool, hour });
  }
  return series;
}

// 24h x 7d heatmap: hour-of-day on x, day on y, intensity 0-1
function genHeatmap(seed = 7) {
  let s = seed;
  const rand = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  const days = 7, hours = 24;
  const grid = [];
  for (let d = 0; d < days; d++) {
    const row = [];
    for (let h = 0; h < hours; h++) {
      const peak = h >= 16 && h <= 22 ? 1 : h >= 9 && h <= 15 ? 0.55 : h >= 6 && h <= 8 ? 0.4 : 0.15;
      const noise = 0.6 + rand() * 0.4;
      row.push(Math.min(1, peak * noise));
    }
    grid.push(row);
  }
  return grid;
}

const ALERTS = [
  { id: 'a1', severity: 'critical', time: '8:42 AM', property: 'Park Lane', network: 'Parking Garage / BBQ Area', device: 'eero Outdoor 7 — LWR STORE RM', message: 'Device offline for 14 minutes', age: '14m' },
  { id: 'a2', severity: 'warning', time: '8:31 AM', property: 'The Pakalana', network: 'Pool Deck', device: 'eero Pro 6E — Cabana 3', message: 'Intermittent signal, 4 disconnects in 1h', age: '25m' },
  { id: 'a3', severity: 'info', time: '8:12 AM', property: 'Hanalei Bay Resort', network: 'Guest WiFi', device: 'AP-NORTH-04', message: 'Auto-recovered after firmware push', age: '44m' },
  { id: 'a4', severity: 'critical', time: '7:58 AM', property: 'Park Lane', network: 'Lobby/Front Desk', device: 'switch-core-01', message: 'Uplink degraded — investigating', age: '58m' },
  { id: 'a5', severity: 'warning', time: '7:14 AM', property: 'Capitol Place', network: 'Conference Rm 2', device: 'eero Pro 6E — CONF2', message: 'High channel utilization (94%)', age: '1h 42m' },
  { id: 'a6', severity: 'info', time: '6:40 AM', property: 'Beach Villas at Koolina', network: 'Maintenance LAN', device: 'switch-mtn-02', message: 'Firmware update completed', age: '2h 16m' },
];

// Per-property mini sparkline (24 points)
function genSpark(seed) {
  let s = seed;
  const rand = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  return Array.from({ length: 24 }, (_, i) => {
    const peak = i >= 16 && i <= 22 ? 1 : i >= 9 && i <= 15 ? 0.6 : 0.25;
    return Math.round(8 + rand() * 6 + peak * 18);
  });
}

PROPERTIES.forEach((p, i) => { p.spark = genSpark(i + 3); });

const SSIDS = ['AKSLobby', 'PoolGuest', 'StaffSecure', 'BBQ-Patio', 'Spa-Wellness', 'Conference'];

// Expose globally
Object.assign(window, {
  ISLANDS, PROPERTIES, ALERTS, SSIDS,
  genTimeSeries, genHeatmap, genSpark,
});
