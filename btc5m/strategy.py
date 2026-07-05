"""Signal logic: momentum-into-close with impulse confirmation.

Unlike the original Novals83 runner (which only checked ask >= threshold),
this implements the full strategy its README advertises:
  1. entry window near close,
  2. side ask >= threshold (crowd skew),
  3. BTC has actually moved >= btc_move_min_usd in the matching direction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import data


@dataclass
class Signal:
    side: str          # 'UP' | 'DOWN'
    ask: float
    bid: float
    spread: float
    btc_move: Optional[float]
    reason: str


@dataclass
class StrategyParams:
    threshold: float = 0.70
    min_entry_seconds_left: int = 60
    max_entry_seconds_left: int = 150
    btc_move_min_usd: float = 70.0
    require_btc_move: bool = True
    max_spread: float = 0.03
    min_top_ask_notional_usd: float = 30.0


def evaluate(market: data.Market, p: StrategyParams) -> tuple[Optional[Signal], str]:
    """Return (signal, status). status explains skips for logging."""
    sec_left = market.seconds_left
    if sec_left < p.min_entry_seconds_left:
        return None, f"skip_too_late ({sec_left:.0f}s left)"
    if sec_left > p.max_entry_seconds_left:
        return None, f"wait_entry_window ({sec_left:.0f}s left)"

    up_bid, up_ask, _, up_ask_notional = data.order_book(market.up_token)
    dn_bid, dn_ask, _, dn_ask_notional = data.order_book(market.down_token)

    btc_move = data.btc_move_in_slot(market.slot_open_ts)

    candidates: list[Signal] = []
    for side, bid, ask, notional in (
        ("UP", up_bid, up_ask, up_ask_notional),
        ("DOWN", dn_bid, dn_ask, dn_ask_notional),
    ):
        if ask is None or bid is None:
            continue
        if ask < p.threshold:
            continue
        spread = max(0.0, ask - bid)
        if spread > p.max_spread:
            continue
        if notional < p.min_top_ask_notional_usd:
            continue
        if p.require_btc_move:
            if btc_move is None:
                continue
            if side == "UP" and btc_move < p.btc_move_min_usd:
                continue
            if side == "DOWN" and btc_move > -p.btc_move_min_usd:
                continue
        candidates.append(Signal(
            side=side, ask=ask, bid=bid, spread=spread, btc_move=btc_move,
            reason=f"ask={ask:.2f}>=thr={p.threshold:.2f}, move={btc_move}",
        ))

    if not candidates:
        return None, (
            f"no_signal up_ask={up_ask} dn_ask={dn_ask} btc_move="
            f"{btc_move if btc_move is None else round(btc_move, 1)}"
        )
    best = sorted(candidates, key=lambda s: s.ask, reverse=True)[0]
    return best, "signal"
