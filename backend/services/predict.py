from backend.models.train import load_model

def run_prediction(input_data):
    """Load model and run prediction."""
    model = load_model("model.pkl")
    return model.predict(input_data)
