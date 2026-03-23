# Real Estate Market Analyzer

A DFW home price prediction model built with Python, scikit-learn, and MongoDB.

## Stack
- **Frontend**: TBD
- **Backend**: Pandas, Numpy, Scikit-learn
- **Database**: MongoDB Atlas
- **ML Model**: HistGradientBoostingRegressor (scikit-learn)

## Setup

1. Clone the repo
   ```bash
   git clone https://github.com/your-username/real-estate-market-analyzer.git
   cd real-estate-market-analyzer
   ```

2. Create a virtual environment
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables
   ```bash
   cp .env.example .env
   
   # Add your MongoDB URI to .env:
   # MONGODB_URI=your_mongodb_atlas_connection_string
   (ask a project team member for this)
   ```

5. Train the model
   ```bash
   python3 -m backend.models.train
   ```
   > Training data is already in MongoDB Atlas, so no data download is required.
   > This generates `backend/models/saved/model.pkl` and `features.pkl` locally.

6. Run the app
   ```bash
   streamlit run frontend/app.py
   ```


To train with a specific model:
```bash
python3 -m backend.models.train --model random_forest
python3 -m backend.models.train --model gradient_boosting
```

## Testing the Model

After training, run this to test a price prediction:

```python
from backend.services.predict import run_prediction
from datetime import date

result = run_prediction(
    input_data={
        "beds": 4,
        "baths": 2.5,
        "sqft": 2500,
        "year_built": 2005,
        "lot_sqft": 8000,
        "zip_code": "75024",
        "garage": True,
        "property_type": "single family"
    },
    target_date=date(2026, 4, 1)  # date(year, month, day) April 1 2026 (optional, defaults to one month in teh future)
)

print(f"Predicted price: ${result:,.0f}")
```

Expected output: `Predicted price: $XXX,XXX`

