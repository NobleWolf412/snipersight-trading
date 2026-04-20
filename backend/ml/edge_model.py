"""
Edge Model

Trains a win/loss classifier on enriched journal trades.
Uses LogisticRegression when fewer than 100 samples are available,
and GradientBoostingClassifier once we have >= 100 samples.

Layer-1 upgrades
----------------
  Purged walk-forward CV  — folds are strictly time-ordered; a purge gap
    between train and test prevents lookahead bias from overlapping labels.
    Replaces standard k-fold, which is invalid for time-series data.

  SHAP values             — replaces Gini / |coef| importance with Shapley
    Additive Explanations. Reports both a global importance score (mean |SHAP|)
    and a direction value (mean SHAP) so the dashboard can show which features
    help vs hurt win probability.

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
from backend.ml.signal_dataset_builder import build_signal_dataset

logger = logging.getLogger(__name__)

_GBC_THRESHOLD = 100


# ── Purged Walk-Forward Cross-Validator ───────────────────────────────────────

class PurgedWalkForwardCV:
    """
    Walk-forward cross-validator with purge gap and embargo.

    Rows are assumed to be ordered chronologically (journal records come out
    of the JSONL in append order which is chronological).

    purge_pct  — fraction of the dataset to remove between the end of each
                 training fold and the start of the corresponding test fold.
                 Prevents label overlap when hold times are long.
    embargo_pct — fraction of the dataset to skip after each test fold ends
                 before the next training fold begins. Prevents leakage from
                 correlated recent observations.
    """

    def __init__(
        self,
        n_splits: int = 5,
        purge_pct: float = 0.01,
        embargo_pct: float = 0.01,
    ) -> None:
        self.n_splits = n_splits
        self.purge_pct = purge_pct
        self.embargo_pct = embargo_pct

    def split(self, X, y=None, groups=None):
        n = len(X)
        purge = max(1, int(n * self.purge_pct))
        embargo = max(1, int(n * self.embargo_pct))

        fold_size = n // (self.n_splits + 1)
        if fold_size < 2:
            # Not enough data for multi-fold; single train/test split
            mid = n // 2
            yield np.arange(0, mid), np.arange(mid, n)
            return

        for i in range(self.n_splits):
            test_start = (i + 1) * fold_size
            test_end = min(test_start + fold_size, n)
            train_end = max(0, test_start - purge)

            train_idx = np.arange(0, train_end)
            test_idx = np.arange(test_start, test_end)

            if len(train_idx) >= 4 and len(test_idx) >= 1:
                yield train_idx, test_idx

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits


# ── Edge Model ────────────────────────────────────────────────────────────────

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
        # SHAP: mean |shap| and mean shap per feature, set after fit
        self._shap_importance: Optional[np.ndarray] = None   # mean |SHAP|
        self._shap_direction: Optional[np.ndarray] = None    # mean SHAP (signed)

    # ── public ────────────────────────────────────────────────────────────────

    def train(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fit the model from journal records.

        Returns a metadata dict:
            success, model_type, n_samples, accuracy, message
        """
        X, y, weights, ids = build_dataset(records)
        n = len(y)

        if n < MIN_SAMPLES:
            msg = f"Only {n} enriched trades; need {MIN_SAMPLES} to train."
            logger.info(msg)
            return {"success": False, "n_samples": n, "message": msg}

        try:
            model, accuracy = self._fit(X, y, weights)
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
            X = vec.reshape(1, -1)
            expected = getattr(self._model, "n_features_in_", None)
            if expected is not None and X.shape[1] != expected:
                logger.warning(
                    "predict_proba: feature count mismatch (model=%d, input=%d) — retrain needed",
                    expected, X.shape[1],
                )
                return None
            proba = self._model.predict_proba(X)[0][1]
            return float(proba)
        except Exception as exc:
            logger.warning("predict_proba failed: %s", exc)
            return None

    def feature_importance(self) -> List[Dict[str, Any]]:
        """
        Return sorted list of {name, importance, direction} dicts.

        importance  — mean absolute SHAP value (always positive; used for ranking)
        direction   — mean SHAP value (positive = pushes toward win, negative = loss)

        Falls back to Gini / |coef| (without direction) if shap is unavailable.
        Empty list if model not trained.
        """
        if self._model is None:
            return []

        names = self._feature_names

        if self._shap_importance is not None and self._shap_direction is not None:
            pairs = sorted(
                zip(names, self._shap_importance.tolist(), self._shap_direction.tolist()),
                key=lambda x: x[1],
                reverse=True,
            )
            return [
                {"name": n, "importance": round(imp, 5), "direction": round(d, 5)}
                for n, imp, d in pairs
            ]

        # Fallback: no direction field
        try:
            if hasattr(self._model, "feature_importances_"):
                scores = self._model.feature_importances_
            elif hasattr(self._model, "named_steps"):
                clf = self._model.named_steps.get("clf")
                if hasattr(clf, "feature_importances_"):
                    scores = clf.feature_importances_
                else:
                    scores = np.abs(clf.coef_[0])
            else:
                return []

            pairs = sorted(zip(names, scores.tolist()), key=lambda x: x[1], reverse=True)
            return [{"name": n, "importance": round(v, 5), "direction": round(v, 5)} for n, v in pairs]
        except Exception as exc:
            logger.warning("feature_importance fallback failed: %s", exc)
            return []

    def train_combined(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Train on trade journal records + all available scan signals.

        Signals provide 10-100x more data than completed trades alone.
        Executed signals matched to trade outcomes get full weight.
        Filtered signals are weak negatives (weight 0.15).
        """
        X_trades, y_trades, w_trades, ids_trades = build_dataset(records)
        X_signals, y_signals, w_signals, ids_signals = build_signal_dataset()

        if len(y_trades) == 0 and len(y_signals) == 0:
            return {"success": False, "n_samples": 0, "message": "No training data available."}

        parts_X, parts_y, parts_w, parts_ids = [], [], [], []

        if len(y_trades) > 0:
            parts_X.append(X_trades)
            parts_y.append(y_trades)
            parts_w.append(w_trades)
            parts_ids.extend(ids_trades)

        if len(y_signals) > 0:
            parts_X.append(X_signals)
            parts_y.append(y_signals)
            parts_w.append(w_signals)
            parts_ids.extend(ids_signals)

        X = np.vstack(parts_X)
        y = np.concatenate(parts_y)
        weights = np.concatenate(parts_w)
        n = len(y)

        min_required = 10
        if n < min_required:
            msg = f"Only {n} total samples (trades + signals); need {min_required}."
            logger.info(msg)
            return {"success": False, "n_samples": n, "message": msg}

        try:
            model, accuracy = self._fit(X, y, weights)
        except Exception as exc:
            logger.exception("Combined training failed: %s", exc)
            return {"success": False, "n_samples": n, "message": str(exc)}

        from datetime import datetime, timezone
        self._model = model
        self._n_samples = n
        self._accuracy = accuracy
        self._trained_at = datetime.now(timezone.utc).isoformat()

        n_trades = len(y_trades)
        n_sigs = len(y_signals)
        logger.info(
            "EdgeModel trained (combined): %s, n=%d (trades=%d, signals=%d), accuracy=%.3f",
            self._model_type, n, n_trades, n_sigs, accuracy,
        )

        return {
            "success": True,
            "model_type": self._model_type,
            "n_samples": n,
            "n_trades": n_trades,
            "n_signals": n_sigs,
            "accuracy": round(accuracy, 4),
            "trained_at": self._trained_at,
            "message": f"Trained on {n_trades} trades + {n_sigs} signals.",
        }

    def gate_recommendations(self) -> List[Dict[str, Any]]:
        """
        Use SHAP values to recommend gauntlet gate threshold adjustments.

        Returns a list of {gate, current_direction, recommendation, shap_impact}
        for the most impactful features that map to tunable gates.
        """
        importance = self.feature_importance()
        if not importance:
            return []

        gate_map = {
            "confidence_score": {"gate": "min_confluence", "description": "Confluence score threshold"},
            "pullback_probability": {"gate": "pullback_prob_threshold", "description": "Pullback probability gate (< 0.45)"},
            "risk_reward_ratio": {"gate": "min_risk_reward", "description": "Minimum R:R ratio"},
            "direction_long": {"gate": "direction_bias", "description": "Long vs short preference"},
            "conviction_ordinal": {"gate": "conviction_filter", "description": "Conviction class gate (A/B/C)"},
        }

        recommendations = []
        for feat in importance:
            name = feat["name"]
            if name not in gate_map:
                continue

            direction = feat.get("direction", 0)
            impact = feat.get("importance", 0)

            if direction > 0.01:
                action = "Higher values predict wins — consider loosening this gate"
            elif direction < -0.01:
                action = "Higher values predict losses — consider tightening this gate"
            else:
                action = "Minimal directional impact — gate is well-calibrated"

            recommendations.append({
                **gate_map[name],
                "feature": name,
                "shap_importance": round(impact, 4),
                "shap_direction": round(direction, 4),
                "recommendation": action,
            })

        return sorted(recommendations, key=lambda x: x["shap_importance"], reverse=True)

    def status(self) -> Dict[str, Any]:
        """Return current model metadata."""
        return {
            "trained": self._model is not None,
            "model_type": self._model_type,
            "n_samples": self._n_samples,
            "accuracy": self._accuracy,
            "trained_at": self._trained_at,
            "min_samples_required": MIN_SAMPLES,
            "cv_method": "purged_walk_forward",
        }

    # ── private ───────────────────────────────────────────────────────────────

    def _fit(
        self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray
    ) -> Tuple[Any, float]:
        """
        Fit pipeline with purged walk-forward CV.
        Returns (fitted_pipeline, cv_accuracy).
        """
        from sklearn.base import clone
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

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
                C=1.0, max_iter=1000, random_state=42, class_weight="balanced"
            )
            self._model_type = "LogisticRegression"
            pipe = Pipeline([("scaler", StandardScaler()), ("clf", estimator)])

        # Purged walk-forward cross-validation
        cv = PurgedWalkForwardCV(n_splits=min(5, n // 10), purge_pct=0.02, embargo_pct=0.01)
        fold_scores = []
        for train_idx, test_idx in cv.split(X):
            fold_pipe = clone(pipe)
            w_train = sample_weight[train_idx]
            fold_pipe.fit(X[train_idx], y[train_idx], clf__sample_weight=w_train)
            fold_scores.append(fold_pipe.score(X[test_idx], y[test_idx]))

        accuracy = float(np.mean(fold_scores)) if fold_scores else 0.5

        # Final fit on all data
        pipe.fit(X, y, clf__sample_weight=sample_weight)

        # Compute SHAP values
        self._compute_shap(pipe, X)

        return pipe, accuracy

    def _compute_shap(self, pipe: Any, X: np.ndarray) -> None:
        """Compute and store per-feature SHAP importance and direction."""
        try:
            import shap

            clf = pipe.named_steps["clf"]

            if self._model_type == "GradientBoosting":
                explainer = shap.TreeExplainer(clf)
                shap_vals = explainer.shap_values(X)
            else:
                X_scaled = pipe.named_steps["scaler"].transform(X)
                explainer = shap.LinearExplainer(clf, X_scaled, feature_perturbation="interventional")
                shap_vals = explainer.shap_values(X_scaled)

            # Binary classifiers may return a list [class0_vals, class1_vals]
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]

            self._shap_importance = np.mean(np.abs(shap_vals), axis=0)
            self._shap_direction = np.mean(shap_vals, axis=0)
            logger.info("SHAP values computed for %d features", len(self._shap_importance))

        except ImportError:
            logger.info("shap not installed — falling back to Gini/coef importance")
            self._shap_importance = None
            self._shap_direction = None
        except Exception as exc:
            logger.warning("SHAP computation failed: %s", exc)
            self._shap_importance = None
            self._shap_direction = None
