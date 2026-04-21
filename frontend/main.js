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
let PRICE_PER_SQFT  = [];
let AVG_YEAR_BUILT  = [];
let MEDIAN_SQFT     = [];
let LISTING_VOLUME  = [];

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
  const zip        = getZipValue();
  const tier       = document.getElementById('f-tier').value;
  const beds       = document.getElementById('f-beds').value;
  const baths      = document.getElementById('f-baths').value;
  const garage     = document.getElementById('f-garage').value;
  const sqft       = document.getElementById('f-sqft').value;

  const lot_sqft   = document.getElementById('f-lot').value;

  const params = new URLSearchParams();
  if (type       !== 'all') params.set('type',       type);
  if (zip        !== 'all') params.set('zip',        zip);
  if (tier       !== 'all') params.set('tier',       tier);
  if (beds       !== 'all') params.set('beds',       beds);
  if (baths      !== 'all') params.set('baths',      baths);
  if (garage     !== 'all') params.set('garage',     garage);
  if (sqft       !== 'all') params.set('sqft',       sqft);
  if (lot_sqft   !== 'all') params.set('lot_sqft',   lot_sqft);
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
    PRICE_PER_SQFT  = d.price_per_sqft  || [];
    AVG_YEAR_BUILT  = d.avg_year_built  || [];
    MEDIAN_SQFT     = d.median_sqft     || [];
    LISTING_VOLUME  = d.listing_volume  || [];
    API_SOURCE      = d.source;

    if (statusEl) {
      const live  = d.source.prices === 'mongodb';
      const freds = d.source.rates  === 'fred';
      statusEl.textContent = live
        ? `API connected : live MongoDB data`
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
};


function getMultiplier(map, val) { return map[val] ?? 1.00; }

// Extract a bare 5-digit ZIP from the combo input (handles "75201 – Dallas", "75201", or "All DFW")
function getZipValue() {
  const raw = (document.getElementById('f-neighborhood').value || '').trim();
  const m   = raw.match(/\b(\d{5})\b/);
  return m ? m[1] : 'all';
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
  const zip    = getZipValue();

  const tierLabels = { entry:'Entry (<$300K)', mid:'Mid ($300K–$500K)', upper:'Upper ($500K–$800K)', luxury:'Luxury (>$800K)' };

  const parts = [];
  if (type  !== 'all') parts.push({ 'single-family':'Single Family', condo:'Condo', townhouse:'Townhouse', 'multi-family':'Multi-Family' }[type]);
  if (beds  !== 'all') parts.push(beds + ' bed');
  if (baths !== 'all') parts.push(baths + ' bath');
  if (tier  !== 'all') parts.push(tierLabels[tier]);
  if (zip   !== 'all') parts.push('ZIP ' + zip);

  return parts.length ? parts.join(' · ') : null;
}


// ---------------------------------------------------------------------------
// Main analysis : reads all controls, scales data, redraws everything
// ---------------------------------------------------------------------------

async function runAnalysis() {
  const type         = 'all';
  const rateScenario = document.getElementById('sel-rate').value;

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
  const rateGrowthPerQ = { current: 0.000, falling: 0.012, rising: -0.009 }[rateScenario] ?? 0;

  // --- Price multipliers ---
  // Skip the type multiplier when the API already returned type-filtered MongoDB data,
  // so we don't double-apply it on top of real segment prices.
  const typeAlreadyFiltered = API_SOURCE.prices === 'mongodb' && type !== 'all';
  // When a specific ZIP is selected the API already returns ZIP-filtered prices,
  // so no additional location multiplier is needed.
  const priceMult = typeAlreadyFiltered ? 1.00 : getMultiplier(PRICE_MULTIPLIERS.type, type);

  // --- Guard: no data for this filter combination ---
  if (LABELS_HIST.length === 0) {
    ['s-price','s-change','s-rate','s-forecast-end','s-ppsf','s-dom','s-sqft','s-volume']
      .forEach(id => { const el = document.getElementById(id); if (el) el.textContent = 'N/A'; });
    document.getElementById('s-price-sub').textContent = 'No data for selected filters';
    destroyChart('price');
    destroyChart('macro');
    return;
  }

  // --- Slice to history window ---
  const histLabels = LABELS_HIST.slice(startIdx, endIdx + 1);
  currentHistLabels = histLabels;
  currentStartIdx   = startIdx;
  const histRates  = MORTGAGE_RATE.slice(startIdx, endIdx + 1).map(r => r ?? null);
  const prices     = BASE_PRICES.slice(startIdx, endIdx + 1).map(p => Math.round(p * priceMult));

  // --- Forecast: ML model via backend ---

  // Build quarter labels dynamically from endIdx forward
  const forecastLabels = [];
  let [fy, fq] = LABELS_HIST[endIdx].split('-Q').map(Number);
  for (let i = 0; i < nForecast; i++) {
    fq++;
    if (fq > 4) { fq = 1; fy++; }
    forecastLabels.push(`${fy}-Q${fq}`);
  }

  const lastPrice = prices[prices.length - 1];

  // Call the ML forecast endpoint; fall back to simple extrapolation if unavailable
  let forecastPrices, ciLower, ciUpper;
  try {
    const fcRes = await fetch(`${API_BASE}/api/forecast`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prices:        prices,
        rates:         histRates,
        n_quarters:    nForecast,
        rate_scenario: rateScenario,
      }),
    });
    if (!fcRes.ok) throw new Error(`HTTP ${fcRes.status}`);
    const fcData = await fcRes.json();
    forecastPrices = fcData.forecast;
    ciLower        = fcData.ci_lower;
    ciUpper        = fcData.ci_upper;
  } catch {
    // Offline fallback: simple geometric extrapolation
    const tail = prices.slice(-8);
    let g = tail.length >= 2
      ? (tail[tail.length - 1] / tail[0]) ** (1 / (tail.length - 1)) - 1
      : 0.008;
    g = Math.max(-0.05, Math.min(0.05, g)) + rateGrowthPerQ;
    forecastPrices = forecastLabels.map((_, i) => Math.round(lastPrice * Math.pow(1 + g, i + 1)));
    ciLower        = forecastPrices.map((f, i) => Math.round(f - lastPrice * 0.022 * (i + 1)));
    ciUpper        = forecastPrices.map((f, i) => Math.round(f + lastPrice * 0.022 * (i + 1)));
  }

  // ciScaled kept for drawPriceChart signature compatibility
  const ciScaled = forecastPrices.map((f, i) => ciUpper[i] - f);

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

  const lastPpsf  = PRICE_PER_SQFT.slice(startIdx, endIdx + 1).filter(v => v != null).at(-1);
  const lastYear  = AVG_YEAR_BUILT.slice(startIdx, endIdx + 1).filter(v => v != null).at(-1);
  const lastSqft  = MEDIAN_SQFT.slice(startIdx, endIdx + 1).filter(v => v != null).at(-1);
  const totalVol  = LISTING_VOLUME.slice(startIdx, endIdx + 1).reduce((s, v) => s + (v || 0), 0);

  document.getElementById('s-ppsf').textContent   = lastPpsf != null ? '$' + lastPpsf.toLocaleString()       : 'N/A';
  document.getElementById('s-dom').textContent    = lastYear != null ? lastYear.toString()                    : 'N/A';
  document.getElementById('s-sqft').textContent   = lastSqft != null ? lastSqft.toLocaleString() + ' sqft'   : 'N/A';
  document.getElementById('s-volume').textContent = totalVol > 0     ? totalVol.toLocaleString()              : 'N/A';

  const forecastEnd = forecastPrices[forecastPrices.length - 1];


  const forecastEndEl = document.getElementById('s-forecast-end');
  forecastEndEl.textContent = fmtPrice(forecastEnd);
  forecastEndEl.className   = forecastEnd >= currentPrice ? 'stat-value up' : 'stat-value down';
  document.getElementById('s-forecast-end-sub').textContent = forecastLabels[forecastLabels.length - 1];

  drawPriceChart(prices, forecastPrices, ciLower, ciUpper, histLabels, forecastLabels);
  drawMacroChart();
}


// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

function drawPriceChart(prices, forecasts, ciLower, ciUpper, histLabels, forecastLabels) {
  destroyChart('price');
  const allLabels    = [...histLabels, ...forecastLabels];
  const anchor       = prices[prices.length - 1];
  const forecastLine = [...Array(prices.length - 1).fill(null), anchor, ...forecasts];
  const upperBand    = [...Array(prices.length - 1).fill(null), anchor, ...ciUpper];
  const lowerBand    = [...Array(prices.length - 1).fill(null), anchor, ...ciLower];

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

// Populate ZIP code datalist from live API
async function loadZipcodes() {
  try {
    const res  = await fetch(`${API_BASE}/api/zipcodes`);
    if (!res.ok) return;
    const zips = await res.json();
    const dl   = document.getElementById('zip-datalist');
    // "All DFW" is already in the HTML; append only the ZIP entries
    zips.forEach(({ zip, city }) => {
      const opt = document.createElement('option');
      opt.value = `${zip} – ${city}`;
      dl.appendChild(opt);
    });
  } catch { /* offline — input still works, just no suggestions */ }
}

// Run Analysis button: full refetch (gets latest real data) + redraw
document.getElementById('run-btn').addEventListener('click', () => {
  loadMarketData().then(() => runAnalysis());
});

// Select all text on focus so the user can immediately type to filter
document.getElementById('f-neighborhood').addEventListener('focus', function () {
  this.select();
});
// Restore default label if left blank
document.getElementById('f-neighborhood').addEventListener('blur', function () {
  if (this.value.trim() === '') this.value = 'All DFW';
});

// ZIP change: reload market data for that ZIP then rerun.
// Fires on datalist selection (change) or when user clears / types a full 5-digit ZIP (input).
let _zipDebounce;
document.getElementById('f-neighborhood').addEventListener('input', () => {
  clearTimeout(_zipDebounce);
  const zip = getZipValue();
  const raw = document.getElementById('f-neighborhood').value.trim();
  // Refetch when value is a valid ZIP, blank, or "All DFW"
  if (zip !== 'all' || raw === '' || raw.toLowerCase() === 'all dfw') {
    _zipDebounce = setTimeout(() => loadMarketData().then(() => runAnalysis()), 400);
  }
});
document.getElementById('f-neighborhood').addEventListener('change', () => {
  loadMarketData().then(() => runAnalysis());
});

// All segment filters hit MongoDB — reload data on change
['f-beds','f-baths','f-tier','f-garage','f-sqft','f-lot'].forEach(id => {
  document.getElementById(id).addEventListener('change', () => {
    loadMarketData().then(() => runAnalysis());
  });
});

// Chart controls only need a redraw, not a data reload
['sel-start','sel-end','sel-periods','sel-rate'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('change', () => runAnalysis());
});

// ---------------------------------------------------------------------------
// Initial load
// ---------------------------------------------------------------------------
loadZipcodes().then(() => loadMarketData()).then(() => runAnalysis());
