"""
Edge Model

Trains a win/loss classifier on enriched journal trades.
Uses LogisticRegression when fewer than 100 samples are available,
and GradientBoostingClassifier once we have ≥100 samples.

This model only affects the dashboard — no live bot behaviour changes.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.ml.feature_extractor import (
    MIN_SAMPLES,
    build_dataset,
    extract_features,
    feature_names,
)

logger = logging.getLogger(__name__)

# Switch to GBC once we have this many enriched trades.
_GBC_THRESHOLD = 100


class EdgeModel:
    """
    Win-probability classifier for completed trades.

    Call `train(records)` to (re-)fit from the journal, then
    `predict_proba(record)` to score an individual trade plan.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._feature_names: List[str] = feature_names()
        self._n_samples: int = 0
        self._model_type: str = "none"
        self._accuracy: float = 0.0
        self._trained_at: Optional[str] = None

    # ── public ────────────────────────────────────────────────────────────────

    def train(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fit the model from journal records.

        Returns a metadata dict with keys:
            success, model_type, n_samples, accuracy, message
        """
        X, y, ids = build_dataset(records)
        n = len(y)

        if n < MIN_SAMPLES:
            msg = f"Only {n} enriched trades; need {MIN_SAMPLES} to train."
            logger.info(msg)
            return {"success": False, "n_samples": n, "message": msg}

        try:
            model, accuracy = self._fit(X, y)
        except Exception as exc:
            logger.exception("Training failed: %s", exc)
            return {"success": False, "n_samples": n, "message": str(exc)}

        from datetime import datetime, timezone
        self._model = model
        self._n_samples = n
        self._accuracy = accuracy
        self._trained_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            "EdgeModel trained: %s, n=%d, accuracy=%.3f",
            self._model_type,
            n,
            accuracy,
        )

        return {
            "success": True,
            "model_type": self._model_type,
            "n_samples": n,
            "accuracy": round(accuracy, 4),
            "trained_at": self._trained_at,
            "message": "Model trained successfully.",
        }

    def predict_proba(self, record: Dict[str, Any]) -> Optional[float]:
        """
        Return probability of a WIN (class=1) for a single record.

        Returns None if the model is not trained or the record is not enriched.
        """
        if self._model is None:
            return None

        vec = extract_features(record)
        if vec is None:
            return None

        try:
            proba = self._model.predict_proba(vec.reshape(1, -1))[0][1]
            return float(proba)
        except Exception as exc:
            logger.warning("predict_proba failed: %s", exc)
            return None

    def feature_importance(self) -> List[Dict[str, Any]]:
        """
        Return sorted list of {name, importance} dicts.

        For GBC uses `feature_importances_`, for LR uses |coef_|.
        Empty list if model not trained.
        """
        if self._model is None:
            return []

        names = self._feature_names
        try:
            if hasattr(self._model, "feature_importances_"):
                scores = self._model.feature_importances_
            else:
                scores = np.abs(self._model.coef_[0])

            pairs = sorted(
                zip(names, scores.tolist()),
                key=lambda x: x[1],
                reverse=True,
            )
            return [{"name": n, "importance": round(v, 5)} for n, v in pairs]
        except Exception as exc:
            logger.warning("feature_importance failed: %s", exc)
            return []

    def status(self) -> Dict[str, Any]:
        """Return current model metadata."""
        return {
            "trained": self._model is not None,
            "model_type": self._model_type,
            "n_samples": self._n_samples,
            "accuracy": self._accuracy,
            "trained_at": self._trained_at,
            "min_samples_required": MIN_SAMPLES,
        }

    # ── private ───────────────────────────────────────────────────────────────

    def _fit(self, X: np.ndarray, y: np.ndarray) -> Tuple[Any, float]:
        """Fit and cross-validate.  Returns (fitted_model, cv_accuracy)."""
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        n = len(y)

        if n >= _GBC_THRESHOLD:
            from sklearn.ensemble import GradientBoostingClassifier
            estimator = GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=3,
                subsample=0.8,
                random_state=42,
            )
            self._model_type = "GradientBoosting"
            pipe = Pipeline([("clf", estimator)])
        else:
            from sklearn.linear_model import LogisticRegression
            estimator = LogisticRegression(
                C=1.0,
                max_iter=1000,
                random_state=42,
                class_weight="balanced",
            )
            self._model_type = "LogisticRegression"
            pipe = Pipeline([("scaler", StandardScaler()), ("clf", estimator)])

        cv_folds = min(5, n // max(int(np.sum(y == 0)), int(np.sum(y == 1)), 1))
        cv_folds = max(cv_folds, 2)

        scores = cross_val_score(pipe, X, y, cv=cv_folds, scoring="accuracy")
        accuracy = float(scores.mean())

        pipe.fit(X, y)
        return pipe, accuracy
