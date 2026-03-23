# Real Estate Market Analyzer

A DFW home price prediction model built with Python, scikit-learn, and MongoDB.

## Stack
- **Frontend**: Streamlit
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
   # MONGODB_DB=real_estate
   ```

5. Train the model
   ```bash
   python3 -m backend.models.train
   ```
   > Training data is already in MongoDB - no data download required.
   > This generates `backend/models/saved/model.pkl` and `features.pkl` locally.

6. Run the app
   ```bash
   streamlit run frontend/app.py
   ```

## Model Performance
| Model | MAE | R² |
|---|---|---|
| Random Forest | $93,286 | 0.692 |
| Gradient Boosting | $94,602 | 0.726 |
| Gradient Boosting + zip code | $87,321 | 0.760 |

The saved model is Gradient Boosting with zip code encoding (best performer).

To train with a specific model:
```bash
python3 -m backend.models.train --model random_forest
python3 -m backend.models.train --model gradient_boosting
```

## Branch Workflow
```bash
git checkout main && git pull
git checkout -b feature/your-name-feature
# make changes
git add .
git commit -m "feat: describe your change"
git push origin feature/your-name-feature
# open a Pull Request into main on GitHub
```
