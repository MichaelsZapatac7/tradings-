"""Signal logic.

Two modes:

- ``fair_value`` (our own strategy): price the binary with a volatility model
  (see model.py) and buy a side only when the model probability exceeds the
  market ask by ``min_edge``. Symmetric — it can buy the cheap underdog when
  the crowd overpays for the favorite, or the favorite while it is still
  underpriced. Edge-based, not hype-based.

- ``threshold`` (momentum-into-close, what the viral Novals83 repo does):
  buy the side whose ask >= threshold, optionally confirmed by a BTC impulse
  (the confirmation its README advertises but its code never implemented).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import data, model


@dataclass
class Signal:
    side: str          # 'UP' | 'DOWN'
    ask: float
    bid: float
    spread: float
    btc_move: Optional[float]
    reason: str
    model_p: Optional[float] = None
    edge: Optional[float] = None


@dataclass
class StrategyParams:
    signal_mode: str = "fair_value"   # 'fair_value' | 'threshold'
    min_edge: float = 0.06
    threshold: float = 0.70
    min_entry_seconds_left: int = 60
    max_entry_seconds_left: int = 150
    btc_move_min_usd: float = 70.0
    require_btc_move: bool = True
    max_spread: float = 0.03
    min_top_ask_notional_usd: float = 30.0
    max_entry_price: float = 0.97


def _books(market: data.Market):
    up_bid, up_ask, _, up_notional = data.order_book(market.up_token)
    dn_bid, dn_ask, _, dn_notional = data.order_book(market.down_token)
    return (("UP", up_bid, up_ask, up_notional), ("DOWN", dn_bid, dn_ask, dn_notional))


def _liquidity_ok(bid, ask, notional, p: StrategyParams) -> bool:
    if ask is None or bid is None:
        return False
    if ask > p.max_entry_price:
        return False
    if (ask - bid) > p.max_spread:
        return False
    return notional >= p.min_top_ask_notional_usd


def evaluate(market: data.Market, p: StrategyParams) -> tuple[Optional[Signal], str]:
    """Return (signal, status). status explains skips for logging."""
    sec_left = market.seconds_left
    if sec_left < p.min_entry_seconds_left:
        return None, f"skip_too_late ({sec_left:.0f}s left)"
    if sec_left > p.max_entry_seconds_left:
        return None, f"wait_entry_window ({sec_left:.0f}s left)"

    sides = _books(market)
    rows = data.kraken_1m_candles()

    if p.signal_mode == "fair_value":
        fv = model.fair_value(market, rows)
        if fv is None:
            return None, "skip_no_model (price feed unavailable)"
        candidates: list[Signal] = []
        for side, bid, ask, notional in sides:
            if not _liquidity_ok(bid, ask, notional, p):
                continue
            mp = fv.p_up if side == "UP" else 1.0 - fv.p_up
            edge = mp - ask
            if edge >= p.min_edge:
                candidates.append(Signal(
                    side=side, ask=ask, bid=bid, spread=ask - bid,
                    btc_move=fv.lead, model_p=round(mp, 4), edge=round(edge, 4),
                    reason=f"model_p={mp:.2f} vs ask={ask:.2f} (edge={edge:+.2f}, "
                           f"lead={fv.lead:+.0f}, vol1m={fv.vol_1m:.0f})",
                ))
        if not candidates:
            asks = {s[0]: s[2] for s in sides}
            return None, (
                f"no_edge p_up={fv.p_up:.2f} up_ask={asks['UP']} dn_ask={asks['DOWN']} "
                f"lead={fv.lead:+.0f} vol1m={fv.vol_1m:.0f}"
            )
        return max(candidates, key=lambda s: s.edge), "signal"

    # threshold mode (Novals83-style momentum into close)
    btc_move = data.btc_move_in_slot(market.slot_open_ts, rows)
    candidates = []
    for side, bid, ask, notional in sides:
        if not _liquidity_ok(bid, ask, notional, p):
            continue
        if ask < p.threshold:
            continue
        if p.require_btc_move:
            if btc_move is None:
                continue
            if side == "UP" and btc_move < p.btc_move_min_usd:
                continue
            if side == "DOWN" and btc_move > -p.btc_move_min_usd:
                continue
        candidates.append(Signal(
            side=side, ask=ask, bid=bid, spread=ask - bid, btc_move=btc_move,
            reason=f"ask={ask:.2f}>=thr={p.threshold:.2f}, move={btc_move}",
        ))
    if not candidates:
        asks = {s[0]: s[2] for s in sides}
        return None, (
            f"no_signal up_ask={asks['UP']} dn_ask={asks['DOWN']} btc_move="
            f"{btc_move if btc_move is None else round(btc_move, 1)}"
        )
    return max(candidates, key=lambda s: s.ask), "signal"
