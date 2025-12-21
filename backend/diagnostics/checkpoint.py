"""
Checkpoint Manager for SniperSight Diagnostic Backtest

Provides save/resume capability for long-running backtests.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import hashlib


@dataclass
class Checkpoint:
    """Represents a backtest checkpoint state."""
    id: str
    timestamp: str
    
    # Progress
    current_mode: str
    modes_completed: List[str]
    modes_remaining: List[str]
    current_symbol: Optional[str]
    symbols_completed: List[str]
    symbols_remaining: List[str]
    
    # Stats so far
    trades_count: int
    signals_count: int
    anomalies_count: int
    
    # Win/loss tracking
    wins_by_mode: Dict[str, int] = field(default_factory=dict)
    losses_by_mode: Dict[str, int] = field(default_factory=dict)
    
    # Config used
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CheckpointManager:
    """
    Manages checkpoint saving and loading for backtest resumability.
    
    Checkpoints are saved as JSON files in a dedicated directory.
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.checkpoints_dir = self.output_dir / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_checkpoint: Optional[Checkpoint] = None
        self._checkpoint_count = 0
    
    def _generate_checkpoint_id(self) -> str:
        """Generate a unique checkpoint ID."""
        self._checkpoint_count += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"cp_{timestamp}_{self._checkpoint_count:04d}"
    
    def create_checkpoint(
        self,
        current_mode: str,
        modes_completed: List[str],
        modes_remaining: List[str],
        current_symbol: Optional[str],
        symbols_completed: List[str],
        symbols_remaining: List[str],
        trades_count: int,
        signals_count: int,
        anomalies_count: int,
        wins_by_mode: Dict[str, int],
        losses_by_mode: Dict[str, int],
        config: Dict[str, Any]
    ) -> Checkpoint:
        """Create a new checkpoint with current state."""
        checkpoint = Checkpoint(
            id=self._generate_checkpoint_id(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            current_mode=current_mode,
            modes_completed=modes_completed,
            modes_remaining=modes_remaining,
            current_symbol=current_symbol,
            symbols_completed=symbols_completed,
            symbols_remaining=symbols_remaining,
            trades_count=trades_count,
            signals_count=signals_count,
            anomalies_count=anomalies_count,
            wins_by_mode=wins_by_mode,
            losses_by_mode=losses_by_mode,
            config=config
        )
        
        self._current_checkpoint = checkpoint
        return checkpoint
    
    def save(self, checkpoint: Optional[Checkpoint] = None) -> Path:
        """Save checkpoint to disk."""
        cp = checkpoint or self._current_checkpoint
        if not cp:
            raise ValueError("No checkpoint to save")
        
        filepath = self.checkpoints_dir / f"{cp.id}.json"
        with open(filepath, "w") as f:
            json.dump(cp.to_dict(), f, indent=2)
        
        # Also save as "latest"
        latest_path = self.checkpoints_dir / "latest.json"
        with open(latest_path, "w") as f:
            json.dump(cp.to_dict(), f, indent=2)
        
        return filepath
    
    def load(self, checkpoint_id: Optional[str] = None) -> Optional[Checkpoint]:
        """
        Load a checkpoint from disk.
        
        Args:
            checkpoint_id: Specific checkpoint ID, or None for latest
            
        Returns:
            Checkpoint object or None if not found
        """
        if checkpoint_id:
            filepath = self.checkpoints_dir / f"{checkpoint_id}.json"
        else:
            filepath = self.checkpoints_dir / "latest.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, "r") as f:
            data = json.load(f)
        
        checkpoint = Checkpoint(**data)
        self._current_checkpoint = checkpoint
        return checkpoint
    
    def list_checkpoints(self) -> List[str]:
        """List all available checkpoint IDs."""
        checkpoints = []
        for f in self.checkpoints_dir.glob("cp_*.json"):
            checkpoints.append(f.stem)
        return sorted(checkpoints)
    
    def get_latest_checkpoint_id(self) -> Optional[str]:
        """Get the ID of the latest checkpoint."""
        latest_path = self.checkpoints_dir / "latest.json"
        if not latest_path.exists():
            return None
        
        with open(latest_path, "r") as f:
            data = json.load(f)
        return data.get("id")
    
    @property
    def current(self) -> Optional[Checkpoint]:
        """Get current checkpoint."""
        return self._current_checkpoint
