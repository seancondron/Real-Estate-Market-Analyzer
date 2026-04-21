from flask import Flask, jsonify, request
from flask_cors import CORS

from backend.services.predict import run_prediction

app = Flask(__name__)
CORS(app)

FORECAST_LABELS = [
    '2022-Q3','2022-Q4',
    '2023-Q1','2023-Q2','2023-Q3','2023-Q4',
    '2024-Q1','2024-Q2','2024-Q3','2024-Q4',
    '2025-Q1','2025-Q2','2025-Q3','2025-Q4',
    '2026-Q1','2026-Q2','2026-Q3','2026-Q4',
    '2027-Q1','2027-Q2','2027-Q3','2027-Q4','2028-Q1',
]

_TYPE_MAP = {
    'single-family': 'single family',
    'condo':         'condo',
    'townhouse':     'townhouse',
    'multi-family':  'multi-family',
}


def _qlabel(year, quarter):
    return f"{int(year)}-Q{int(quarter)}"


def _quarter_sort_key(label):
    yr, qtr = label.split('-Q')
    return int(yr) * 4 + int(qtr)


def _try_get_real_data(property_type=None):
    result = {}
    try:
        from backend.db.mongodb import db
        from backend.db.schema import DFW_CITIES

        # FRED mortgage rates — monthly → quarterly averages
        rate_docs = list(db['mortgage_rates'].find(
            {}, {'_id': 0, 'year': 1, 'month': 1, 'mortgage_rate_30y': 1}
        ))
        if rate_docs:
            by_q = {}
            for d in rate_docs:
                key = _qlabel(d['year'], (d['month'] - 1) // 3 + 1)
                by_q.setdefault(key, []).append(d['mortgage_rate_30y'])
            result['mortgage_rates'] = {k: round(sum(v) / len(v), 3) for k, v in by_q.items()}

        # Properties — quarterly avg price, all available years
        match = {
            'price': {'$gt': 10_000, '$lt': 10_000_000},
            'city':  {'$in': [c.title() for c in DFW_CITIES]},
        }
        if property_type and property_type != 'all':
            match['property_type'] = {'$regex': _TYPE_MAP.get(property_type, property_type), '$options': 'i'}

        pipeline = [
            {'$match': match},
            {'$addFields': {'_d': {'$toDate': '$date_posted'}}},
            {'$match': {'_d': {'$type': 'date'}}},
            {'$addFields': {
                '_yr':  {'$year': '$_d'},
                '_qtr': {'$toInt': {'$ceil': {'$divide': [{'$month': '$_d'}, 3]}}},
            }},
            {'$match': {'_yr': {'$gte': 2010, '$lte': 2026}}},
            {'$group': {
                '_id':       {'year': '$_yr', 'quarter': '$_qtr'},
                'avg_price': {'$avg': '$price'},
                'count':     {'$sum': 1},
            }},
            {'$sort': {'_id.year': 1, '_id.quarter': 1}},
        ]
        price_docs = list(db['properties'].aggregate(pipeline))
        if price_docs:
            result['prices'] = {
                _qlabel(d['_id']['year'], d['_id']['quarter']): round(d['avg_price'])
                for d in price_docs
            }

    except Exception:
        pass

    return result


def _build_response(real, property_type=None):
    # Only use quarters with real MongoDB prices — no estimates
    if 'prices' not in real or len(real['prices']) < 2:
        return {'error': 'no data', 'source': {'prices': 'none', 'rates': 'none'},
                'labels_hist': [], 'labels_forecast': FORECAST_LABELS,
                'base_prices': [], 'base_forecast': [], 'confidence_intervals': [],
                'mortgage_rate': [], 'unemployment': []}

    hist_labels = sorted(real['prices'].keys(), key=_quarter_sort_key)
    prices = [real['prices'][lbl] for lbl in hist_labels]

    # Forecast: extrapolate from trend of last 4 real quarters
    recent = prices[-4:]
    growth = (recent[-1] / recent[0]) ** (1 / max(len(recent) - 1, 1)) if recent[0] > 0 else 1.008
    last = prices[-1]
    forecast = [round(last * (growth ** i)) for i in range(1, len(FORECAST_LABELS) + 1)]
    ci = [round(last * 0.020 * (i + 1)) for i in range(len(FORECAST_LABELS))]

    # FRED rates for every historical quarter
    rates_source = 'baseline'
    rates = []
    for lbl in hist_labels:
        if 'mortgage_rates' in real and lbl in real['mortgage_rates']:
            rates.append(round(real['mortgage_rates'][lbl], 2))
            rates_source = 'fred'
        else:
            rates.append(None)

    return {
        'source':               {'prices': 'mongodb', 'rates': rates_source},
        'labels_hist':          hist_labels,
        'labels_forecast':      FORECAST_LABELS,
        'base_prices':          prices,
        'base_forecast':        forecast,
        'confidence_intervals': ci,
        'mortgage_rate':        rates,
        'unemployment':         [None] * len(hist_labels),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/api/health')
def health():
    return jsonify({'status': 'ok'})


@app.get('/api/market-data')
def market_data():
    property_type = request.args.get('type')
    real = _try_get_real_data(property_type=property_type)
    return jsonify(_build_response(real, property_type=property_type))


@app.post('/api/predict')
def predict():
    body = request.get_json(silent=True) or {}
    required = ['beds', 'baths', 'sqft', 'year_built', 'zip_code']
    missing = [f for f in required if f not in body]
    if missing:
        return jsonify({'error': f"Missing fields: {', '.join(missing)}"}), 400
    try:
        price = run_prediction({
            'beds':          float(body['beds']),
            'baths':         float(body['baths']),
            'sqft':          float(body['sqft']),
            'year_built':    int(body['year_built']),
            'lot_sqft':      float(body.get('lot_sqft', 6000)),
            'median_income': float(body.get('median_income', 65000)),
            'garage':        bool(body.get('garage', True)),
            'property_type': str(body.get('property_type', 'single family')),
            'zip_code':      str(body['zip_code']),
        })
        return jsonify({'predicted_price': round(price, 2)})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


if __name__ == '__main__':
    app.run(port=5001, debug=True)
