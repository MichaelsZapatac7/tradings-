"""Main loop: watch the current BTC 5m market, enter on signal, manage exit.

Exit modes:
  - hold: hold to resolution (winner pays $1/share, loser $0). Avoids paying
    the exit spread; PnL comes from settlement. Default.
  - before_close: sell at bid N seconds before close (original skill behavior).
Both modes honor the stop-loss while the position is open.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from . import data
from .executor import make_executor
from .risk import RiskManager
from .strategy import StrategyParams, evaluate


@dataclass
class RunnerParams:
    stake_usd: float = 5.0
    stop_loss_pct: float = 0.25
    exit_mode: str = "hold"           # 'hold' | 'before_close'
    exit_before_sec: int = 20
    poll_sec: float = 5.0
    session_minutes: int = 60
    daily_max_loss_usd: float = 15.0
    max_trades_per_day: int = 12
    execute: bool = False


def _log(runtime_dir: Path, record: dict[str, Any]) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    with (runtime_dir / "trades.jsonl").open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _wait_resolution(slug: str, end_ts: float, timeout_sec: float = 180.0) -> Optional[str]:
    while time.time() < end_ts + timeout_sec:
        if time.time() >= end_ts + 5:
            res = data.market_resolution(slug)
            if res:
                return res
        time.sleep(5)
    return None


def run_session(sp: StrategyParams, rp: RunnerParams, runtime_dir: Path) -> None:
    ex = make_executor(rp.execute)
    risk = RiskManager(runtime_dir, rp.daily_max_loss_usd, rp.max_trades_per_day)
    deadline = time.time() + rp.session_minutes * 60
    print(f"[btc5m] mode={ex.mode} session={rp.session_minutes}min "
          f"stake=${rp.stake_usd} exit={rp.exit_mode} threshold={sp.threshold}")

    while time.time() < deadline:
        allowed, why = risk.can_trade()
        if not allowed:
            print(f"[btc5m] HALT: {why}")
            return

        m = data.current_5m_market()
        if not m:
            time.sleep(rp.poll_sec)
            continue

        try:
            sig, status = evaluate(m, sp)
        except Exception as e:
            print(f"[btc5m] {data.ts_utc()} {m.slug} data_error: {e}")
            time.sleep(rp.poll_sec)
            continue

        print(f"[btc5m] {data.ts_utc()} {m.slug} {m.seconds_left:.0f}s {status}")
        if not sig:
            time.sleep(rp.poll_sec)
            continue

        token = m.token_for(sig.side)
        fill = ex.buy(token, sig.ask, rp.stake_usd)
        if not fill.ok:
            print(f"[btc5m] entry FAILED: {fill.error}")
            time.sleep(rp.poll_sec)
            continue

        trade: dict[str, Any] = {
            "ts": data.ts_utc(), "mode": ex.mode, "slug": m.slug,
            "side": sig.side, "signal": asdict(sig),
            "entry": asdict(fill),
        }
        print(f"[btc5m] ENTER {sig.side} @{fill.price:.3f} "
              f"shares={fill.shares} cost=${fill.usd:.2f} ({sig.reason})")

        pnl = _manage_position(ex, m, sig.side, token, fill, sp, rp, trade)
        trade["pnl_usd"] = pnl
        risk.record_trade(pnl if pnl is not None else 0.0)
        _log(runtime_dir, trade)
        print(f"[btc5m] CLOSED {m.slug} pnl=${pnl}")

    print("[btc5m] session finished")


def _manage_position(ex, m: data.Market, side: str, token: str, entry,
                     sp: StrategyParams, rp: RunnerParams,
                     trade: dict[str, Any]) -> Optional[float]:
    sl_price = entry.price * (1.0 - rp.stop_loss_pct)
    trade["stop_loss_price"] = round(sl_price, 4)

    while True:
        sec_left = m.seconds_left
        if rp.exit_mode == "before_close" and sec_left <= rp.exit_before_sec:
            bid, _, _, _ = data.order_book(token)
            px = bid if bid is not None else 0.0
            fill = ex.sell(token, px, entry.shares)
            trade["exit"] = {"reason": "time_exit", **asdict(fill)}
            return round(fill.usd - entry.usd, 6) if fill.ok else None
        if sec_left <= 2:
            break
        try:
            bid, _, _, _ = data.order_book(token)
        except Exception:
            bid = None
        if bid is not None and bid <= sl_price:
            fill = ex.sell(token, bid, entry.shares)
            trade["exit"] = {"reason": "stop_loss", **asdict(fill)}
            return round(fill.usd - entry.usd, 6) if fill.ok else None
        time.sleep(min(rp.poll_sec, max(1.0, sec_left / 4)))

    # hold to resolution
    res = _wait_resolution(m.slug, m.end_ts)
    won = (res == side) if res else None
    payout = round(entry.shares * (1.0 if won else 0.0), 6) if won is not None else None
    trade["exit"] = {"reason": "resolution", "resolved": res, "won": won, "payout_usd": payout}
    if payout is None:
        return None
    return round(payout - entry.usd, 6)
