const API_BASE = 'http://localhost:5001';

// ---------------------------------------------------------------------------
// Market data arrays : loaded from API on startup; hardcoded values are the
// offline fallback so the dashboard always renders something.
// ---------------------------------------------------------------------------

let LABELS_HIST     = ['2015-Q1','2015-Q2','2015-Q3','2015-Q4','2016-Q1','2016-Q2','2016-Q3','2016-Q4','2017-Q1','2017-Q2','2017-Q3','2017-Q4','2018-Q1','2018-Q2','2018-Q3','2018-Q4','2019-Q1','2019-Q2','2019-Q3','2019-Q4','2020-Q1','2020-Q2','2020-Q3','2020-Q4','2021-Q1','2021-Q2','2021-Q3','2021-Q4','2022-Q1','2022-Q2'];
let LABELS_FORECAST = ['2022-Q3','2022-Q4','2023-Q1','2023-Q2','2023-Q3','2023-Q4','2024-Q1','2024-Q2','2024-Q3','2024-Q4','2025-Q1','2025-Q2','2025-Q3','2025-Q4','2026-Q1','2026-Q2','2026-Q3','2026-Q4','2027-Q1','2027-Q2','2027-Q3','2027-Q4','2028-Q1'];
let BASE_PRICES     = [320000,325000,330000,328000,318000,322000,335000,330000,328000,332000,340000,338000,335000,342000,350000,345000,340000,345000,348000,344000,342000,348000,358000,370000,390000,410000,405000,395000,365000,395000];
let BASE_FORECAST   = [385000,370000,358000,362000,368000,375000,380000,378000,372000,376000,382000,388000,391000,396000,400000,403000,406200,409400,412600,415900,419300,422600,426000];
let CI              = [8000,16000,25000,35000,44000,53000,63000,74000,84000,94000,104000,114000,124000,134000,144000,154000,164000,174000,184000,194000,204000,214000,224000];
let MORTGAGE_RATE   = [3.7,3.9,3.9,3.9,3.7,3.6,3.5,3.5,4.2,3.9,3.8,3.9,4.4,4.6,4.6,4.6,4.4,4.1,3.6,3.7,3.5,3.2,2.9,2.7,2.7,3.0,2.9,3.1,3.9,5.1];
let UNEMPLOYMENT    = [4.0,3.9,3.8,3.7,3.6,3.5,3.4,3.4,3.3,3.3,3.2,3.2,3.1,3.0,2.9,2.9,2.8,2.8,2.7,2.7,2.7,2.8,3.5,4.0,4.5,4.5,4.5,4.0,3.1,2.9];

const MACRO_FEATURES = {
  mortgage_rate: { label: 'Mortgage Rate %', color: '#d29922', getData: () => MORTGAGE_RATE },
};

let selectedMacroFeatures = new Set(['mortgage_rate']);
let currentHistLabels = [];
let currentStartIdx = 0;

// Tracks which data came from MongoDB vs the hardcoded baseline.
// Used to avoid double-applying segment multipliers when the API already
// filtered by property type.
let API_SOURCE = { prices: 'baseline', rates: 'baseline', inventory: 'baseline' };


// ---------------------------------------------------------------------------
// API: load market data (passes current type filter so MongoDB can segment)
// ---------------------------------------------------------------------------

async function loadMarketData() {
  const statusEl = document.getElementById('api-status');
  const type     = 'all';

  const params = new URLSearchParams();
  if (type !== 'all') params.set('type', type);
  const url = `${API_BASE}/api/market-data${params.size ? '?' + params : ''}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const d = await res.json();

    LABELS_HIST     = d.labels_hist;
    LABELS_FORECAST = d.labels_forecast;
    BASE_PRICES     = d.base_prices;
    BASE_FORECAST   = d.base_forecast;
    CI              = d.confidence_intervals;
    MORTGAGE_RATE   = d.mortgage_rate;
    UNEMPLOYMENT    = d.unemployment;
    API_SOURCE      = d.source;

    if (statusEl) {
      const live  = d.source.prices === 'mongodb';
      const freds = d.source.rates  === 'fred';
      statusEl.textContent = live
        ? `API connected : ${freds ? 'FRED rates' : 'cached rates'}`
        : `API connected : ${freds ? 'FRED rates' : 'cached data'}`;
      statusEl.style.color = (live || freds) ? 'var(--green)' : 'var(--accent)';
    }
  } catch {
    if (statusEl) {
      statusEl.textContent = 'API offline : using cached data';
      statusEl.style.color = 'var(--yellow)';
    }
  }
}


// ---------------------------------------------------------------------------
// Segment multipliers
// ---------------------------------------------------------------------------

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


function getMultiplier(map, val) { return map[val] ?? 1.00; }


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
  if (v == null) return ':';
  return '$' + Math.round(v).toLocaleString();
}





// ---------------------------------------------------------------------------
// Segment description bar
// ---------------------------------------------------------------------------

function buildSegmentDesc() {
  const type   = 'all';
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
// Main analysis : reads all controls, scales data, redraws everything
// ---------------------------------------------------------------------------

function runAnalysis() {
  const type  = 'all';
  const beds  = document.getElementById('f-beds').value;
  const baths = document.getElementById('f-baths').value;
  const tier  = document.getElementById('f-tier').value;
  const hood  = document.getElementById('f-neighborhood').value;

  // --- History window ---
  const startQ   = document.getElementById('sel-start').value;
  const endQ     = document.getElementById('sel-end').value;
  let   startIdx = LABELS_HIST.indexOf(startQ);
  let   endIdx   = LABELS_HIST.indexOf(endQ);
  if (startIdx < 0) startIdx = 0;
  if (endIdx   < 0 || endIdx < startIdx) endIdx = LABELS_HIST.length - 1;

  // --- Forecast quarters ---
  const nForecast = parseInt(document.getElementById('sel-periods').value, 10);

  // --- Rate scenario: adjusts forecast prices per quarter ---
  // Falling rates → buyers can afford more → prices rise; rising rates → inverse
  const rateScenario = document.getElementById('sel-rate').value;
  const rateGrowthPerQ = { current: 0.000, falling: 0.012, rising: -0.009 }[rateScenario] ?? 0;

  // --- Price multipliers ---
  // Skip the type multiplier when the API already returned type-filtered MongoDB data,
  // so we don't double-apply it on top of real segment prices.
  const typeAlreadyFiltered = API_SOURCE.prices === 'mongodb' && type !== 'all';
  const priceMult =
    (typeAlreadyFiltered ? 1.00 : getMultiplier(PRICE_MULTIPLIERS.type, type)) *
    getMultiplier(PRICE_MULTIPLIERS.beds,         beds)  *
    getMultiplier(PRICE_MULTIPLIERS.baths,        baths) *
    getMultiplier(PRICE_MULTIPLIERS.tier,         tier)  *
    getMultiplier(PRICE_MULTIPLIERS.neighborhood, hood);

  // --- Slice to history window ---
  const histLabels = LABELS_HIST.slice(startIdx, endIdx + 1);
  currentHistLabels = histLabels;
  currentStartIdx   = startIdx;
  const histRates  = MORTGAGE_RATE.slice(startIdx, endIdx + 1).map(r => r ?? null);
  const prices     = BASE_PRICES.slice(startIdx, endIdx + 1).map(p => Math.round(p * priceMult));

  // --- Forecast: always anchors to the last visible history quarter ---

  // Build quarter labels dynamically from endIdx forward
  const forecastLabels = [];
  let [fy, fq] = LABELS_HIST[endIdx].split('-Q').map(Number);
  for (let i = 0; i < nForecast; i++) {
    fq++;
    if (fq > 4) { fq = 1; fy++; }
    forecastLabels.push(`${fy}-Q${fq}`);
  }

  // Derive quarterly growth rate from the last 4 visible history points
  const tail = prices.slice(-4);
  let baseGrowth = tail.length >= 2
    ? (tail[tail.length - 1] / tail[0]) ** (1 / (tail.length - 1)) - 1
    : 0.008;
  baseGrowth = Math.max(-0.05, Math.min(0.05, baseGrowth)); // clamp runaway extrapolation

  const lastPrice = prices[prices.length - 1];
  const forecastPrices = forecastLabels.map((_, i) =>
    Math.round(lastPrice * Math.pow(1 + baseGrowth + rateGrowthPerQ, i + 1))
  );

  // CI widens ~2.2% of last price per quarter
  const ciScaled = forecastLabels.map((_, i) =>
    Math.round(lastPrice * 0.022 * (i + 1))
  );

  // --- Segment bar ---
  const segDesc = buildSegmentDesc();
  const segBar  = document.getElementById('segment-bar');
  if (segDesc) {
    segBar.style.display = 'block';
    document.getElementById('segment-desc').textContent = segDesc;
    document.getElementById('price-badge').textContent  = segDesc;
  } else {
    segBar.style.display = 'none';
    document.getElementById('price-badge').textContent = 'All Types · All DFW';
  }

  // --- Stat cards ---
  const currentPrice = prices[prices.length - 1];
  const firstPrice   = prices[0];
  const pctChange    = ((currentPrice - firstPrice) / firstPrice * 100);
  const changeSign   = pctChange >= 0 ? '+' : '';
  const currentRate  = histRates[histRates.length - 1];

  document.getElementById('s-price').textContent     = fmtPrice(currentPrice);
  document.getElementById('s-price-sub').textContent =
    'Dallas-Fort Worth, TX' + (segDesc ? ' · ' + segDesc : ' · All Types');

  const changeEl = document.getElementById('s-change');
  changeEl.textContent = `${changeSign}${pctChange.toFixed(1)}%`;
  changeEl.className   = pctChange >= 0 ? 'stat-value up' : 'stat-value down';
  document.getElementById('s-change-sub').textContent = `${histLabels[0]} to ${histLabels[histLabels.length - 1]}`;

  document.getElementById('s-rate').textContent = currentRate != null ? currentRate.toFixed(1) + '%' : 'N/A';

  // --- Factor cards ---
  const rateDescMap = {
    current: 'Scenario: Rates Hold. Elevated rates limit purchasing power.',
    falling: 'Scenario: Rates Fall (−0.5/qtr). Improving affordability boosts demand and prices.',
    rising:  'Scenario: Rates Rise (+0.4/qtr). Higher rates compress purchasing power and slow price growth.',
  };
  const forecastEnd    = forecastPrices[forecastPrices.length - 1];
  const forecastTrend  = forecastEnd > currentPrice ? 'upward trend projected' : 'flat/declining trend projected';
  const forecastPeriod = `${forecastLabels[0]} to ${forecastLabels[forecastLabels.length - 1]}`;

  document.getElementById('fc-rate-val').textContent      = currentRate != null ? currentRate.toFixed(1) + '% (30yr fixed)' : 'N/A';
  document.getElementById('fc-rate-desc').textContent     = rateDescMap[rateScenario];
  document.getElementById('fc-forecast-val').textContent  = fmtPrice(forecastEnd);
  document.getElementById('fc-forecast-desc').textContent = `${forecastPeriod} : ${forecastTrend}`;

  drawPriceChart(prices, forecastPrices, ciScaled, histLabels, forecastLabels);
  drawMacroChart();
}


// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

function drawPriceChart(prices, forecasts, ci, histLabels, forecastLabels) {
  destroyChart('price');
  const allLabels    = [...histLabels, ...forecastLabels];
  const forecastLine = [...Array(prices.length - 1).fill(null), prices[prices.length - 1], ...forecasts];
  const upperBand    = [...Array(prices.length - 1).fill(null), prices[prices.length - 1], ...forecasts.map((f, i) => f + ci[i])];
  const lowerBand    = [...Array(prices.length - 1).fill(null), prices[prices.length - 1], ...forecasts.map((f, i) => f - ci[i])];

  charts['price'] = new Chart(document.getElementById('priceChart'), {
    type: 'line',
    data: {
      labels: allLabels,
      datasets: [
        {
          label: 'Historical',
          data: [...prices, ...Array(forecastLabels.length).fill(null)],
          borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,0.06)',
          borderWidth: 2, pointRadius: 3, fill: true, tension: 0.3,
        },
        {
          label: 'Forecast',
          data: forecastLine,
          borderColor: '#3fb950', borderDash: [5, 4],
          borderWidth: 2, pointRadius: 2, tension: 0.3, fill: false, pointStyle: 'line',
        },
        {
          label: 'CI Upper',
          data: upperBand,
          borderColor: 'rgba(63,185,80,0.2)', backgroundColor: 'rgba(63,185,80,0.07)',
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
        y: { grid: { color: GRID_COLOR }, ticks: { callback: v => '$' + (v / 1000).toFixed(0) + 'K' } },
      },
    },
  });
}

function toggleMacroFeature(key) {
  if (selectedMacroFeatures.has(key) && selectedMacroFeatures.size === 1) return;
  if (selectedMacroFeatures.has(key)) {
    selectedMacroFeatures.delete(key);
  } else {
    selectedMacroFeatures.add(key);
  }
  document.querySelectorAll('.feature-chip').forEach(el => {
    el.classList.toggle('active', selectedMacroFeatures.has(el.dataset.feature));
  });
  drawMacroChart();
}

function drawMacroChart() {
  destroyChart('macro');
  const len      = currentHistLabels.length;
  const datasets = [];

  datasets.push({
    label: 'Mortgage Rate %',
    data: MORTGAGE_RATE.slice(currentStartIdx, currentStartIdx + len),
    borderColor: '#d29922', borderWidth: 2, pointRadius: 2, tension: 0.3,
  });

  charts['macro'] = new Chart(document.getElementById('macroChart'), {
    type: 'line',
    data: { labels: currentHistLabels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: true, labels: { boxWidth: 10, padding: 12 } }, tooltip: TOOLTIP_BASE },
      scales: {
        x: { grid: { color: GRID_COLOR } },
        y: { grid: { color: GRID_COLOR }, position: 'left', title: { display: true, text: 'Mortgage %', color: '#d29922' } },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Price prediction : calls the Flask ML endpoint
// ---------------------------------------------------------------------------

async function runPredict() {
  const btn     = document.getElementById('predict-btn');
  const priceEl = document.getElementById('pred-price');
  const noteEl  = document.getElementById('pred-note');

  btn.disabled    = true;
  btn.textContent = 'Predicting…';
  priceEl.textContent = '…';
  noteEl.textContent  = '';

  const body = {
    property_type: document.getElementById('p-type').value,
    beds:          document.getElementById('p-beds').value,
    baths:         document.getElementById('p-baths').value,
    sqft:          document.getElementById('p-sqft').value,
    year_built:    document.getElementById('p-year').value,
    lot_sqft:      document.getElementById('p-lot').value,
    zip_code:      document.getElementById('p-zip').value,
    garage:        document.getElementById('p-garage').checked,
  };

  try {
    const res  = await fetch(`${API_BASE}/api/predict`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    priceEl.textContent = fmtPrice(data.predicted_price);
    noteEl.textContent  = `${body.property_type} · ${body.beds}bd/${body.baths}ba · ${Number(body.sqft).toLocaleString()} sqft · ZIP ${body.zip_code}`;
  } catch (err) {
    priceEl.textContent = 'Error';
    noteEl.textContent  = err.message;
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Predict Price';
  }
}


// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------

// Run Analysis button: full refetch (gets latest real data) + redraw
document.getElementById('run-btn').addEventListener('click', () => {
  loadMarketData().then(() => runAnalysis());
});

// ---------------------------------------------------------------------------
// Initial load
// ---------------------------------------------------------------------------
loadMarketData().then(() => runAnalysis());
