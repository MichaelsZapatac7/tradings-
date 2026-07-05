"""Daily risk limits persisted across runs (runtime/risk_state.json)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


class RiskManager:
    def __init__(self, runtime_dir: Path, daily_max_loss_usd: float, max_trades_per_day: int):
        self.path = runtime_dir / "risk_state.json"
        self.daily_max_loss_usd = float(daily_max_loss_usd)
        self.max_trades_per_day = int(max_trades_per_day)
        self.state = self._load()

    def _today(self) -> str:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    def _load(self) -> dict:
        try:
            s = json.loads(self.path.read_text())
        except Exception:
            s = {}
        if s.get("day") != self._today():
            s = {"day": self._today(), "realized_pnl_usd": 0.0, "trades": 0}
        return s

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))

    def can_trade(self) -> tuple[bool, str]:
        self.state = self._load()
        if self.state["trades"] >= self.max_trades_per_day:
            return False, f"max_trades_per_day reached ({self.max_trades_per_day})"
        if self.state["realized_pnl_usd"] <= -self.daily_max_loss_usd:
            return False, (
                f"daily loss cap hit ({self.state['realized_pnl_usd']:.2f} <= "
                f"-{self.daily_max_loss_usd:.2f} USD)"
            )
        return True, "ok"

    def record_trade(self, pnl_usd: float) -> None:
        self.state = self._load()
        self.state["trades"] += 1
        self.state["realized_pnl_usd"] = round(self.state["realized_pnl_usd"] + pnl_usd, 6)
        self._save()
