"""
Model Store

Handles serialization and loading of the EdgeModel to/from disk,
and provides a module-level singleton for use throughout the backend.
"""

import json
import logging
import os
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MODEL_PATH = "backend/cache/edge_model.joblib"
_META_PATH = "backend/cache/edge_model_meta.json"

_lock = threading.Lock()
_instance: Optional["ManagedEdgeModel"] = None


class ManagedEdgeModel:
    """
    Wraps EdgeModel with disk persistence.

    On first access the saved model is auto-loaded if it exists on disk.
    """

    def __init__(
        self,
        model_path: str = _MODEL_PATH,
        meta_path: str = _META_PATH,
    ) -> None:
        self.model_path = model_path
        self.meta_path = meta_path
        self._edge_model: Optional[Any] = None  # EdgeModel, lazy-imported
        self._loaded = False

    # ── public ────────────────────────────────────────────────────────────────

    def train(self, records) -> Dict[str, Any]:
        model = self._get_model()
        result = model.train(records)
        if result.get("success"):
            self._save(model)
        return result

    def train_combined(self, records) -> Dict[str, Any]:
        model = self._get_model()
        result = model.train_combined(records)
        if result.get("success"):
            self._save(model)
        return result

    def predict_proba(self, record: Dict[str, Any]) -> Optional[float]:
        return self._get_model().predict_proba(record)

    def feature_importance(self):
        return self._get_model().feature_importance()

    def gate_recommendations(self):
        return self._get_model().gate_recommendations()

    def status(self) -> Dict[str, Any]:
        return self._get_model().status()

    # ── persistence ───────────────────────────────────────────────────────────

    def _get_model(self):
        if not self._loaded:
            self._load()
        return self._edge_model

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def _save(self, model) -> None:
        try:
            import joblib
            self._ensure_dir()
            joblib.dump(model, self.model_path)
            meta = model.status()
            with open(self.meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            logger.info("EdgeModel saved to %s", self.model_path)
        except Exception as exc:
            logger.error("Failed to save EdgeModel: %s", exc)

    def _load(self) -> None:
        from backend.ml.edge_model import EdgeModel

        self._loaded = True

        if not os.path.exists(self.model_path):
            self._edge_model = EdgeModel()
            return

        try:
            import joblib
            loaded = joblib.load(self.model_path)
            if isinstance(loaded, EdgeModel):
                self._edge_model = loaded
                logger.info(
                    "EdgeModel loaded from %s (n=%d, acc=%.3f)",
                    self.model_path,
                    loaded._n_samples,
                    loaded._accuracy,
                )
            else:
                logger.warning("Unexpected object in %s; starting fresh", self.model_path)
                self._edge_model = EdgeModel()
        except Exception as exc:
            logger.error("Failed to load EdgeModel: %s; starting fresh", exc)
            self._edge_model = EdgeModel()


def get_model_store() -> ManagedEdgeModel:
    """Return the process-wide ManagedEdgeModel singleton."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ManagedEdgeModel()
    return _instance
