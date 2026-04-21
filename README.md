# Real Estate Market Analyzer

A DFW home price analysis and prediction tool built with Python, Flask, scikit-learn, MongoDB, and a vanilla JS frontend.

## Stack
- **Frontend**: HTML/CSS/JavaScript (Chart.js)
- **Backend**: Flask, Pandas, Scikit-learn
- **Database**: MongoDB Atlas
- **ML Model**: Random Forest / Gradient Boosting (scikit-learn)

---

## Getting Started

### Prerequisites
- Python 3.9+
- Access to the MongoDB Atlas cluster (ask a team member for the connection string)

### 1. Clone the repo
```bash
git clone https://github.com/your-username/real-estate-market-analyzer.git
cd real-estate-market-analyzer
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
```

Open `.env` and fill in:
```
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?appName=<AppName>
MONGODB_DB=real_estate
```

### 5. Train the model
```bash
python3 -m backend.models.train
```

This pulls training data from MongoDB and writes two files locally:
- `backend/models/saved/model.pkl`
- `backend/models/saved/features.pkl`

To train with a specific algorithm:
```bash
python3 -m backend.models.train --model random_forest
python3 -m backend.models.train --model gradient_boosting
```

### 6. Start the Flask API
```bash
python3 -m backend.api.app
```

The API runs on `http://localhost:5001`.

### 7. Open the frontend

Open `frontend/index.html` directly in a browser, or serve it with any static file server:
```bash
npx serve frontend
```

The dashboard connects to the Flask API automatically. If the API is offline it falls back to cached data so the charts still render.

---

## Testing the ML model

```bash
python3 -c "
from backend.services.predict import run_prediction
from datetime import date

result = run_prediction(
    input_data={
        'beds': 3,
        'baths': 2,
        'sqft': 1800,
        'year_built': 2000,
        'lot_sqft': 6000,
        'zip_code': '75024',
        'garage': True,
        'property_type': 'single family'
    },
    target_date=date(2026, 4, 1)
)
print(f'Predicted price: \${result:,.0f}')
"
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/market-data` | Historical prices, mortgage rates, forecast data |
| POST | `/api/predict` | ML price prediction for a specific property |
| GET | `/api/health` | Health check |
