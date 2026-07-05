"""Market data access: Polymarket Gamma/CLOB and BTC spot price (Coinbase).

Binance is geo-blocked from many datacenters (HTTP 451), so the BTC price
source defaults to Coinbase Exchange public candles.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from typing import Any, Optional

import requests

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"

UTC = dt.timezone.utc
_HEADERS = {"User-Agent": "btc5m-bot/1.0"}


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def ts_utc() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def bucket_5m(ts: Optional[int] = None) -> int:
    t = int(ts if ts is not None else time.time())
    return t - (t % 300)


def _get(url: str, params: Optional[dict] = None, timeout: int = 12) -> Any:
    r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _parse_json_field(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


class Market:
    """Normalized view of one BTC 5m Up/Down market."""

    def __init__(self, raw: dict[str, Any], slug: str):
        self.raw = raw
        self.slug = slug
        outcomes = _parse_json_field(raw.get("outcomes")) or []
        prices = _parse_json_field(raw.get("outcomePrices")) or []
        token_ids = _parse_json_field(raw.get("clobTokenIds")) or []
        if len(prices) < 2 or len(token_ids) < 2:
            raise ValueError("market missing outcomePrices/clobTokenIds")

        up_i, down_i = 0, 1
        labs = [str(x).lower() for x in outcomes[:2]]
        if len(labs) >= 2 and ("up" in labs[1] or "yes" in labs[1]):
            up_i, down_i = 1, 0

        self.up_price = float(prices[up_i])
        self.down_price = float(prices[down_i])
        self.up_token = str(token_ids[up_i])
        self.down_token = str(token_ids[down_i])
        self.end_iso = str(raw.get("endDate") or raw.get("endDateIso") or "")
        self.end_ts = dt.datetime.fromisoformat(self.end_iso.replace("Z", "+00:00")).timestamp()
        self.closed = bool(raw.get("closed"))
        self.active = raw.get("active") is not False

    @property
    def seconds_left(self) -> float:
        return max(0.0, self.end_ts - time.time())

    @property
    def slot_open_ts(self) -> int:
        return int(self.end_ts) - 300

    def token_for(self, side: str) -> str:
        return self.up_token if side == "UP" else self.down_token


def fetch_event(slug: str) -> Optional[dict[str, Any]]:
    arr = _get(f"{GAMMA_BASE}/events", params={"slug": slug})
    return arr[0] if arr else None


def current_5m_market() -> Optional[Market]:
    """Active BTC 5m market for the current slot, or None."""
    slug = f"btc-updown-5m-{bucket_5m()}"
    try:
        ev = fetch_event(slug)
    except Exception:
        return None
    mkts = (ev or {}).get("markets") or []
    if not mkts:
        return None
    try:
        m = Market(mkts[0], slug)
    except Exception:
        return None
    if m.closed or not m.active or m.seconds_left <= 5:
        return None
    return m


def order_book(token_id: str) -> tuple[Optional[float], Optional[float], float, float]:
    """Return (best_bid, best_ask, bid_notional_usd, ask_notional_usd) for a token."""
    book = _get(f"{CLOB_BASE}/book", params={"token_id": token_id})
    best_bid, best_ask = None, None
    bid_notional = ask_notional = 0.0
    for b in book.get("bids", []) or []:
        p, s = float(b["price"]), float(b["size"])
        if best_bid is None or p > best_bid:
            best_bid, bid_notional = p, p * s
    for a in book.get("asks", []) or []:
        p, s = float(a["price"]), float(a["size"])
        if best_ask is None or p < best_ask:
            best_ask, ask_notional = p, p * s
    return best_bid, best_ask, bid_notional, ask_notional


def kraken_1m_candles() -> Optional[list]:
    """Kraken 1m OHLC rows, oldest first, including the in-progress candle.

    Kraken serves the current candle in real time (Binance is geo-blocked
    from many hosts and Coinbase candles lag ~5 minutes).
    Row format: [time, open, high, low, close, vwap, volume, count].
    """
    try:
        d = _get(KRAKEN_OHLC, params={"pair": "XBTUSD", "interval": 1})
        key = next(k for k in d["result"] if k != "last")
        return d["result"][key]
    except Exception:
        return None


def btc_move_in_slot(slot_open_ts: int, rows: Optional[list] = None) -> Optional[float]:
    """Signed BTC-USD move (current price - price at slot open)."""
    if rows is None:
        rows = kraken_1m_candles()
    if not rows:
        return None
    open_px = None
    prev_close = None
    for row in rows:
        t = int(row[0])
        if t < slot_open_ts:
            prev_close = float(row[4])
        elif t == slot_open_ts:
            open_px = float(row[1])
            break
    if open_px is None:
        open_px = prev_close  # no trades in the slot's first minute yet
    if open_px is None or not rows:
        return None
    last_close = float(rows[-1][4])
    return last_close - open_px


def market_resolution(slug: str) -> Optional[str]:
    """After close: 'UP', 'DOWN' or None if not resolved yet."""
    try:
        ev = fetch_event(slug)
    except Exception:
        return None
    mkts = (ev or {}).get("markets") or []
    if not mkts:
        return None
    raw = mkts[0]
    prices = _parse_json_field(raw.get("outcomePrices")) or []
    outcomes = _parse_json_field(raw.get("outcomes")) or []
    if len(prices) < 2 or len(outcomes) < 2:
        return None
    vals = [float(p) for p in prices[:2]]
    if max(vals) < 0.99:
        return None
    win = outcomes[vals.index(max(vals))]
    return "UP" if "up" in str(win).lower() else "DOWN"
