import joblib
import numpy as np

model = joblib.load("models/trained_model.pkl")
scaler = joblib.load("models/scaler.pkl")