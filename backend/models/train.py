import joblib
import os

def save_model(model, filename: str):
    """Save a trained model to disk."""
    path = os.path.join(os.path.dirname(__file__), "saved", filename)
    joblib.dump(model, path)
    print(f"Model saved to {path}")

def load_model(filename: str):
    """Load a saved model from disk."""
    path = os.path.join(os.path.dirname(__file__), "saved", filename)
    return joblib.load(path)
