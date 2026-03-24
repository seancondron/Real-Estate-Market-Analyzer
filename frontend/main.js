// ---------------------------------------------------------------------------
// Base market data — full DFW, all property types combined.
// When filters are active, these arrays get adjusted by a segment multiplier
// so the charts reflect how that slice of the market behaves differently.
// ---------------------------------------------------------------------------

const LABELS_HIST = [
  '2022-Q1','2022-Q2','2022-Q3','2022-Q4',
  '2023-Q1','2023-Q2','2023-Q3','2023-Q4',
  '2024-Q1','2024-Q2','2024-Q3','2024-Q4',
  '2025-Q1','2025-Q2','2025-Q3','2025-Q4',
  '2026-Q1',
];
const LABELS_FORECAST = ['2026-Q2','2026-Q3','2026-Q4','2027-Q1'];
const ALL_LABELS = [...LABELS_HIST, ...LABELS_FORECAST];

const BASE_PRICES = [
  365000,395000,385000,360000,
  348000,350000,358000,362000,
  368000,375000,380000,378000,
  372000,376000,382000,388000,
  391000,
];
const BASE_FORECAST   = [396000,400000,403000,406200];
const BASE_INVENTORY  = [8200,6500,7800,11000,13000,14500,13800,12500,12000,11500,11000,10800,11200,12000,11800,11500,11300];
const CI              = [8000,16000,25000,35000];
const MORTGAGE_RATE   = [3.9,5.1,6.0,6.4,6.5,6.8,7.2,6.8,6.9,7.0,6.7,6.5,6.8,6.9,6.7,6.4,6.6];
const UNEMPLOYMENT    = [3.1,2.9,2.8,3.0,3.3,3.4,3.5,3.6,3.7,3.8,3.8,3.9,4.0,4.1,4.0,4.0,4.1];

// Segment multipliers — how each filter option shifts median price and inventory
// relative to the whole-market baseline. These are based on typical DFW patterns.
const PRICE_MULTIPLIERS = {
  type: { all:1.00, 'single-family':1.12, condo:0.72, townhouse:0.88, 'multi-family':1.35 },
  beds: { all:1.00, '1':0.62, '2':0.81, '3':1.00, '4':1.28, '5+':1.65 },
  baths:{ all:1.00, '1':0.70, '2':0.92, '3':1.15, '4+':1.40 },
  tier: { all:1.00, entry:0.68, mid:0.95, upper:1.45, luxury:2.40 },
  neighborhood: {
    all:1.00, downtown:1.10, uptown:1.22, lakewood:1.18,
    'preston-hollow':1.85, 'bishop-arts':1.05, frisco:1.08, plano:1.02, mckinney:0.96,
  },
};

const INVENTORY_MULTIPLIERS = {
  type: { all:1.00, 'single-family':1.20, condo:0.55, townhouse:0.30, 'multi-family':0.15 },
  tier: { all:1.00, entry:0.60, mid:1.10, upper:0.75, luxury:0.25 },
  neighborhood: {
    all:1.00, downtown:0.40, uptown:0.35, lakewood:0.45,
    'preston-hollow':0.20, 'bishop-arts':0.30, frisco:0.65, plano:0.70, mckinney:0.75,
  },
};

function getMultiplier(map, val) {
  return map[val] ?? 1.00;
}

// Build a human-readable description of active filters for the segment bar
function buildSegmentDesc() {
  const type   = document.getElementById('f-type').value;
  const beds   = document.getElementById('f-beds').value;
  const baths  = document.getElementById('f-baths').value;
  const tier   = document.getElementById('f-tier').value;
  const hood   = document.getElementById('f-neighborhood').value;

  const labels = {
    type:  { 'single-family':'Single Family', condo:'Condo', townhouse:'Townhouse', 'multi-family':'Multi-Family' },
    tier:  { entry:'Entry (<$300K)', mid:'Mid ($300K–$500K)', upper:'Upper ($500K–$800K)', luxury:'Luxury (>$800K)' },
    hood:  { downtown:'Downtown Dallas', uptown:'Uptown', lakewood:'Lakewood', 'preston-hollow':'Preston Hollow', 'bishop-arts':'Bishop Arts', frisco:'Frisco', plano:'Plano', mckinney:'McKinney' },
  };

  const parts = [];
  if (type  !== 'all') parts.push(labels.type[type]);
  if (beds  !== 'all') parts.push(beds + ' bed');
  if (baths !== 'all') parts.push(baths + ' bath');
  if (tier  !== 'all') parts.push(labels.tier[tier]);
  if (hood  !== 'all') parts.push(labels.hood[hood]);

  return parts.length ? parts.join(' · ') : null;
}


// ---------------------------------------------------------------------------
// Chart setup
// ---------------------------------------------------------------------------

const charts = {};

Chart.defaults.color = '#8b949e';
Chart.defaults.font.family = "'JetBrains Mono', monospace";
Chart.defaults.font.size = 10;

const GRID_COLOR   = 'rgba(255,255,255,0.05)';
const TOOLTIP_BASE = {
  backgroundColor: '#1c2128',
  borderColor:     '#30363d',
  borderWidth:     1,
  titleColor:      '#8b949e',
  bodyColor:       '#e6edf3',
};

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function fmtPrice(v) {
  if (v == null) return '—';
  return '$' + Math.round(v).toLocaleString();
}


// ---------------------------------------------------------------------------
// Geo risk slider — label only
// ---------------------------------------------------------------------------

const GEO_LABELS = [
  [-1.0,'Very Unstable'],[-0.5,'Unstable'],[0.0,'Neutral'],[0.5,'Stable'],[1.0,'Very Stable'],
];

function getGeoLabel(val) {
  return GEO_LABELS.reduce((p, c) => Math.abs(c[0]-val) < Math.abs(p[0]-val) ? c : p)[1];
}

document.getElementById('geo-risk').addEventListener('input', function () {
  document.getElementById('geo-val').textContent = getGeoLabel(parseFloat(this.value));
});


// ---------------------------------------------------------------------------
// Main — reads all filters, scales the data, redraws everything
// ---------------------------------------------------------------------------

function runAnalysis() {
  const type  = document.getElementById('f-type').value;
  const beds  = document.getElementById('f-beds').value;
  const baths = document.getElementById('f-baths').value;
  const tier  = document.getElementById('f-tier').value;
  const hood  = document.getElementById('f-neighborhood').value;

  // Combined price multiplier from all active segment filters
  const priceMult =
    getMultiplier(PRICE_MULTIPLIERS.type, type)  *
    getMultiplier(PRICE_MULTIPLIERS.beds, beds)  *
    getMultiplier(PRICE_MULTIPLIERS.baths, baths)*
    getMultiplier(PRICE_MULTIPLIERS.tier, tier)  *
    getMultiplier(PRICE_MULTIPLIERS.neighborhood, hood);

  // Inventory is mostly driven by type and tier, not bedrooms
  const invMult =
    getMultiplier(INVENTORY_MULTIPLIERS.type, type) *
    getMultiplier(INVENTORY_MULTIPLIERS.tier, tier) *
    getMultiplier(INVENTORY_MULTIPLIERS.neighborhood, hood);

  const prices    = BASE_PRICES.map(p => Math.round(p * priceMult));
  const forecasts = BASE_FORECAST.map(p => Math.round(p * priceMult));
  const inventory = BASE_INVENTORY.map(v => Math.round(v * invMult));
  const ciScaled  = CI.map(v => Math.round(v * priceMult));

  // Update segment bar and chart badges
  const segDesc = buildSegmentDesc();
  const segBar  = document.getElementById('segment-bar');
  if (segDesc) {
    segBar.style.display = 'block';
    document.getElementById('segment-desc').textContent = segDesc;
    document.getElementById('price-badge').textContent  = segDesc;
    document.getElementById('inv-badge').textContent    = segDesc;
  } else {
    segBar.style.display = 'none';
    document.getElementById('price-badge').textContent = 'All Types · All DFW';
    document.getElementById('inv-badge').textContent   = 'All Types';
  }

  // Update stat card subtitle
  document.getElementById('s-price-sub').textContent =
    'Dallas-Fort Worth, TX' + (segDesc ? ' · ' + segDesc : ' · All Types');

  drawPriceChart(prices, forecasts, ciScaled);
  drawMacroChart();
  drawInventoryChart(inventory);
  drawScatterChart(prices, inventory);
}


// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

function drawPriceChart(prices, forecasts, ci) {
  destroyChart('price');

  const forecastLine = [...Array(prices.length - 1).fill(null), prices[prices.length - 1], ...forecasts];
  const upperBand    = [...Array(prices.length - 1).fill(null), prices[prices.length - 1], ...forecasts.map((f,i) => f + ci[i])];
  const lowerBand    = [...Array(prices.length - 1).fill(null), prices[prices.length - 1], ...forecasts.map((f,i) => f - ci[i])];

  charts['price'] = new Chart(document.getElementById('priceChart'), {
    type: 'line',
    data: {
      labels: ALL_LABELS,
      datasets: [
        {
          label: 'Historical',
          data: [...prices, ...Array(LABELS_FORECAST.length).fill(null)],
          borderColor: '#58a6ff',
          backgroundColor: 'rgba(88,166,255,0.06)',
          borderWidth: 2, pointRadius: 3, fill: true, tension: 0.3,
        },
        {
          label: 'Forecast',
          data: forecastLine,
          borderColor: '#3fb950',
          borderDash: [5,4],
          borderWidth: 2, pointRadius: 2, tension: 0.3, fill: false, pointStyle: 'line',
        },
        {
          label: 'CI Upper',
          data: upperBand,
          borderColor: 'rgba(63,185,80,0.2)',
          backgroundColor: 'rgba(63,185,80,0.07)',
          borderWidth: 1, pointRadius: 0, fill: '+1', tension: 0.3,
        },
        {
          label: 'CI Lower',
          data: lowerBand,
          borderColor: 'rgba(63,185,80,0.2)',
          borderWidth: 1, pointRadius: 0, fill: false, tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: {
            boxWidth: 10, padding: 14, usePointStyle: true,
            filter: item => item.text !== 'CI Upper' && item.text !== 'CI Lower',
          },
        },
        tooltip: { ...TOOLTIP_BASE, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmtPrice(ctx.raw)}` } },
      },
      scales: {
        x: { grid: { color: GRID_COLOR } },
        y: { grid: { color: GRID_COLOR }, ticks: { callback: v => '$' + (v/1000).toFixed(0) + 'K' } },
      },
    },
  });
}

function drawMacroChart() {
  destroyChart('macro');
  charts['macro'] = new Chart(document.getElementById('macroChart'), {
    type: 'line',
    data: {
      labels: LABELS_HIST,
      datasets: [
        { label:'Mortgage Rate %', data:MORTGAGE_RATE, borderColor:'#d29922', borderWidth:2, pointRadius:2, tension:0.3, yAxisID:'y' },
        { label:'Unemployment %',  data:UNEMPLOYMENT,  borderColor:'#f85149', borderWidth:2, pointRadius:2, tension:0.3, yAxisID:'y1' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display:true, labels:{ boxWidth:10, padding:12 } }, tooltip: TOOLTIP_BASE },
      scales: {
        x:  { grid: { color: GRID_COLOR } },
        y:  { grid: { color: GRID_COLOR }, position:'left',  title:{ display:true, text:'Mortgage %',    color:'#d29922' } },
        y1: { grid: { drawOnChartArea:false }, position:'right', title:{ display:true, text:'Unemployment %', color:'#f85149' } },
      },
    },
  });
}

function drawInventoryChart(inventory) {
  destroyChart('inv');
  charts['inv'] = new Chart(document.getElementById('invChart'), {
    type: 'bar',
    data: {
      labels: LABELS_HIST,
      datasets: [{ label:'Active Listings', data:inventory, backgroundColor:'rgba(88,166,255,0.3)', borderColor:'#58a6ff', borderWidth:1, borderRadius:3 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend:{ display:false }, tooltip: TOOLTIP_BASE },
      scales: {
        x: { grid: { color: GRID_COLOR } },
        y: { grid: { color: GRID_COLOR }, ticks: { callback: v => v.toLocaleString() } },
      },
    },
  });
}

function drawScatterChart(prices, inventory) {
  destroyChart('scatter');
  const points = prices.map((price, i) => ({ x: inventory[i], y: price, label: LABELS_HIST[i] }));
  charts['scatter'] = new Chart(document.getElementById('scatterChart'), {
    type: 'scatter',
    data: {
      datasets: [{ data:points, backgroundColor:'rgba(88,166,255,0.6)', borderColor:'#58a6ff', borderWidth:1, pointRadius:5, pointHoverRadius:7 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display:false },
        tooltip: { ...TOOLTIP_BASE, callbacks: { label: ctx => ` ${ctx.raw.label}: ${fmtPrice(ctx.raw.y)} | ${ctx.raw.x.toLocaleString()} listings` } },
      },
      scales: {
        x: { grid:{ color:GRID_COLOR }, title:{ display:true, text:'Active Listings', color:'#8b949e' } },
        y: { grid:{ color:GRID_COLOR }, ticks:{ callback: v => '$'+(v/1000).toFixed(0)+'K' }, title:{ display:true, text:'Median Price', color:'#8b949e' } },
      },
    },
  });
}

// draw on load
runAnalysis();
