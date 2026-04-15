import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor, ExtraTreesRegressor
from sklearn.linear_model import Ridge, Lasso
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

from backend.data.loader import fetch_properties
from backend.data.processor import build_features


def save_model(model, filename: str):
    """Save a trained model locally (disk)."""
    path = os.path.join(os.path.dirname(__file__), "saved", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)
    print(f"Model saved to {path}")


def load_model(filename: str):
    """Load a saved model from disk."""
    path = os.path.join(os.path.dirname(__file__), "saved", filename)
    return joblib.load(path)


LUXURY_THRESHOLD = 600_000  # homes above this price get their own model
# Soft routing band: blend standard + luxury predictions between these bounds
ROUTE_LOW = 450_000
ROUTE_HIGH = 750_000


def _build_model(model_type: str):
    if model_type == "gradient_boosting":
        return HistGradientBoostingRegressor(max_iter=200, max_depth=5, learning_rate=0.1, random_state=42)
    elif model_type == "extra_trees":
        return ExtraTreesRegressor(n_estimators=200, n_jobs=-1, random_state=42)
    elif model_type == "ridge":
        return Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler()), ("model", Ridge(alpha=1.0))])
    elif model_type == "lasso":
        return Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler()), ("model", Lasso(alpha=1.0, max_iter=5000))])
    elif model_type == "svr":
        return Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler()), ("model", SVR(kernel="rbf", C=100, epsilon=0.1))])
    elif model_type == "xgboost":
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42, n_jobs=-1)
    elif model_type == "lightgbm":
        from lightgbm import LGBMRegressor
        return LGBMRegressor(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42, n_jobs=-1)
    else:
        return RandomForestRegressor(n_estimators=200, max_depth=None, n_jobs=-1, random_state=42)


def train(model_type: str = "random_forest") -> None:
    print("Fetching properties from MongoDB...")
    records = fetch_properties()
    if not records:
        raise RuntimeError("No properties found in MongoDB. Run ingestion first.")

    df = pd.DataFrame(records)
    print(f"Loaded {len(df)} properties")

    print("Building features...")
    X, y = build_features(df)
    print(f"Training on {len(X)} rows with {X.shape[1]} features: {list(X.columns)}")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Log-transform target — real estate prices are log-normal
    y_train_log = np.log1p(y_train)

    model = _build_model(model_type)
    print(f"Training {model_type}...")
    model.fit(X_train, y_train_log)

    preds_log = model.predict(X_test)
    preds = np.expm1(preds_log)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"MAE:  ${mae:,.0f}")
    print(f"R²:   {r2:.3f}")

    save_model(model, "model.pkl")

    # Save feature column order for use in predict.py
    feature_path = os.path.join(os.path.dirname(__file__), "saved", "features.pkl")
    joblib.dump(list(X.columns), feature_path)
    print(f"Feature list saved to {feature_path}")


def train_segmented(model_type: str = "random_forest") -> None:
    """
    Train two specialist models:
      - model_standard.pkl  trained on homes < LUXURY_THRESHOLD
      - model_luxury.pkl    trained on homes >= LUXURY_THRESHOLD

    At prediction time, the standard model runs first; its estimate is used
    to blend between the two models in the ROUTE_LOW–ROUTE_HIGH band.
    """
    print("Fetching properties from MongoDB...")
    records = fetch_properties()
    if not records:
        raise RuntimeError("No properties found in MongoDB. Run ingestion first.")

    df = pd.DataFrame(records)
    print(f"Loaded {len(df)} properties")

    print("Building features...")
    X, y = build_features(df)
    feature_cols = list(X.columns)
    print(f"{len(X)} rows, {X.shape[1]} features")

    # --- shared test split (stratified by luxury flag so both segments are evaluated) ---
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # --- segment masks (applied to train set only; test set stays whole for eval) ---
    std_mask = y_train < LUXURY_THRESHOLD
    lux_mask = y_train >= LUXURY_THRESHOLD
    print(f"\nStandard segment (<${LUXURY_THRESHOLD:,}): {std_mask.sum()} train rows")
    print(f"Luxury segment  (>=${LUXURY_THRESHOLD:,}): {lux_mask.sum()} train rows")

    # --- standard model ---
    print(f"\nTraining standard {model_type}...")
    m_std = _build_model(model_type)
    m_std.fit(X_train[std_mask], np.log1p(y_train[std_mask]))

    # --- luxury model ---
    print(f"Training luxury {model_type}...")
    m_lux = _build_model(model_type)
    m_lux.fit(X_train[lux_mask], np.log1p(y_train[lux_mask]))

    # --- evaluate each segment independently ---
    std_test = y_test < LUXURY_THRESHOLD
    lux_test = y_test >= LUXURY_THRESHOLD

    preds_std_only = np.expm1(m_std.predict(X_test[std_test]))
    mae_std = mean_absolute_error(y_test[std_test], preds_std_only)
    r2_std = r2_score(y_test[std_test], preds_std_only)
    print(f"\nStandard model on standard homes — MAE: ${mae_std:,.0f}  R²: {r2_std:.3f}  (n={std_test.sum()})")

    preds_lux_only = np.expm1(m_lux.predict(X_test[lux_test]))
    mae_lux = mean_absolute_error(y_test[lux_test], preds_lux_only)
    r2_lux = r2_score(y_test[lux_test], preds_lux_only)
    print(f"Luxury model on luxury homes   — MAE: ${mae_lux:,.0f}  R²: {r2_lux:.3f}  (n={lux_test.sum()})")

    # --- blended evaluation on full test set ---
    # Route using zip_encoded (average price in the zip from training data) —
    # a stable proxy for whether the area is standard or luxury.
    # Blend linearly between ROUTE_LOW and ROUTE_HIGH.
    raw_std = np.expm1(m_std.predict(X_test))
    raw_lux = np.expm1(m_lux.predict(X_test))

    if "zip_encoded" in X_test.columns:
        route_signal = X_test["zip_encoded"].values
    else:
        route_signal = raw_std  # fallback

    alpha = np.clip((route_signal - ROUTE_LOW) / (ROUTE_HIGH - ROUTE_LOW), 0.0, 1.0)
    blended = (1 - alpha) * raw_std + alpha * raw_lux

    mae_blended = mean_absolute_error(y_test, blended)
    r2_blended = r2_score(y_test, blended)
    print(f"\nBlended via zip_encoded signal — MAE: ${mae_blended:,.0f}  R²: {r2_blended:.3f}")

    # Hard-routing reference: route entirely by zip_encoded threshold
    hard_route_lux = route_signal >= LUXURY_THRESHOLD
    hard_preds = np.where(hard_route_lux, raw_lux, raw_std)
    mae_hard = mean_absolute_error(y_test, hard_preds)
    print(f"Hard routing (zip >= ${LUXURY_THRESHOLD:,}) — MAE: ${mae_hard:,.0f}")

    # --- save ---
    save_model(m_std, "model_standard.pkl")
    save_model(m_lux, "model_luxury.pkl")

    meta = {
        "luxury_threshold": LUXURY_THRESHOLD,
        "route_low": ROUTE_LOW,
        "route_high": ROUTE_HIGH,
        "model_type": model_type,
        "feature_cols": feature_cols,
    }
    meta_path = os.path.join(os.path.dirname(__file__), "saved", "segmented_meta.pkl")
    joblib.dump(meta, meta_path)

    feature_path = os.path.join(os.path.dirname(__file__), "saved", "features.pkl")
    joblib.dump(feature_cols, feature_path)
    print(f"\nFeature list saved to {feature_path}")


def cross_validate(model_type: str = "random_forest", n_splits: int = 5) -> None:
    """
    K-fold cross-validation on the training data.

    Target encoding (zip_encoded, city_encoded) is refit on each training fold,
    preventing leakage from the validation fold into the feature values.
    The 20% test split is never touched here — CV is used purely for tuning decisions.
    """
    from sklearn.model_selection import KFold

    print("Fetching properties from MongoDB...")
    records = fetch_properties()
    if not records:
        raise RuntimeError("No properties found in MongoDB. Run ingestion first.")

    df = pd.DataFrame(records)
    print(f"Loaded {len(df)} properties")

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    indices = np.arange(len(df))
    maes, r2s = [], []

    for fold, (train_idx, val_idx) in enumerate(kf.split(indices), 1):
        df_train = df.iloc[train_idx].reset_index(drop=True)
        df_val = df.iloc[val_idx].reset_index(drop=True)

        # Target encoding is fit only on the training fold — no leakage
        X_train, y_train = build_features(df_train)
        X_val, y_val = build_features(df_val)

        # Align columns: val fold may be missing rare categories
        for col in X_train.columns:
            if col not in X_val.columns:
                X_val[col] = 0
        X_val = X_val[X_train.columns]

        model = _build_model(model_type)
        model.fit(X_train, np.log1p(y_train))
        preds = np.expm1(model.predict(X_val))

        mae = mean_absolute_error(y_val, preds)
        r2 = r2_score(y_val, preds)
        maes.append(mae)
        r2s.append(r2)
        print(f"  Fold {fold}/{n_splits}: MAE=${mae:,.0f}  R²={r2:.3f}")

    print(f"\nCV MAE:  ${np.mean(maes):,.0f} ± ${np.std(maes):,.0f}")
    print(f"CV R²:   {np.mean(r2s):.3f} ± {np.std(r2s):.3f}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="random_forest", choices=[
        "random_forest", "gradient_boosting", "extra_trees",
        "ridge", "lasso", "svr", "xgboost", "lightgbm"
    ])
    parser.add_argument("--segmented", action="store_true", help="Train separate standard/luxury models")
    parser.add_argument("--cv", action="store_true", help="Run k-fold cross-validation instead of training")
    parser.add_argument("--folds", type=int, default=5, help="Number of CV folds (default: 5)")
    args = parser.parse_args()
    if args.cv:
        cross_validate(args.model, n_splits=args.folds)
    elif args.segmented:
        train_segmented(args.model)
    else:
        train(args.model)
