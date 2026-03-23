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
   # MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?appName=<AppName>
   # MONGODB_DB=real_estate
   # (ask a project team member for this)
   ```

5. Train the model
   ```bash
   python3 -m backend.models.train
   ```
   > Training data is already in MongoDB Atlas, so no data download is required.
   > This generates `backend/models/saved/model.pkl` and `features.pkl` locally.

   To train with a specific model:
   ```bash
   python3 -m backend.models.train --model random_forest
   python3 -m backend.models.train --model gradient_boosting
   ```

6. Run the app
   ```bash
   streamlit run frontend/app.py
   ```

## Testing the Model

After training, run this to test a price prediction:

```python
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

Expected output: 
`Predicted price: $XXX,XXX`

