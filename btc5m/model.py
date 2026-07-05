"""Fair-value model for the 5m Up/Down binary.

With `s` seconds left, the market resolves UP iff the final price exceeds the
slot open price. Treating short-horizon BTC as driftless Brownian motion with
dollar volatility sigma (estimated from recent 1m moves):

    P(UP) = Phi( lead / (sigma_1m * sqrt(s / 60)) )

where `lead` is the current lead over the slot open. This is the standard
price of a cash-or-nothing binary near expiry. The strategy buys a side only
when this model probability exceeds the market ask by `min_edge`, which must
cover spread, slippage, fees and model error.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Optional

from . import data


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def dollar_vol_1m(rows: list, lookback: int = 30) -> Optional[float]:
    """Std deviation of 1-minute close-to-close dollar moves.

    Excludes the in-progress candle (its move is truncated).
    """
    closes = [float(r[4]) for r in rows[:-1]][-(lookback + 1):]
    if len(closes) < 10:
        return None
    diffs = [closes[i + 1] - closes[i] for i in range(len(closes) - 1)]
    vol = statistics.pstdev(diffs)
    return vol if vol > 0 else None


@dataclass
class FairValue:
    p_up: float
    lead: float
    vol_1m: float
    seconds_left: float


def fair_value(market: data.Market, rows: Optional[list] = None) -> Optional[FairValue]:
    if rows is None:
        rows = data.kraken_1m_candles()
    if not rows:
        return None
    lead = data.btc_move_in_slot(market.slot_open_ts, rows)
    vol = dollar_vol_1m(rows)
    if lead is None or vol is None:
        return None
    sec_left = max(1.0, market.seconds_left)
    sigma = vol * math.sqrt(sec_left / 60.0)
    p_up = norm_cdf(lead / sigma)
    return FairValue(p_up=p_up, lead=lead, vol_1m=vol, seconds_left=sec_left)
