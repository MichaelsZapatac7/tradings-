"""Trade execution: paper (default) and live (Polymarket CLOB).

Live mode is self-contained via py-clob-client — it does NOT depend on the
private `pm-hl-conservative-plus-repo` that the original Novals83 skill
shells out to. Requires env vars:
  PM_PRIVATE_KEY   (Polygon wallet private key)
  PM_FUNDER        (proxy/funder address, optional depending on wallet type)
  PM_SIGNATURE_TYPE (default 2)
API creds are derived automatically if PM_API_KEY/SECRET/PASSPHRASE are unset.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Fill:
    ok: bool
    price: float
    shares: float
    usd: float
    order_id: Optional[str] = None
    error: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


class PaperExecutor:
    """Simulates fills at the observed top of book (no slippage modeling
    beyond crossing the spread: buys at ask, sells at bid)."""

    mode = "paper"

    def buy(self, token_id: str, ask: float, stake_usd: float) -> Fill:
        shares = round(stake_usd / ask, 6)
        return Fill(ok=True, price=ask, shares=shares, usd=round(shares * ask, 6))

    def sell(self, token_id: str, bid: float, shares: float) -> Fill:
        return Fill(ok=True, price=bid, shares=shares, usd=round(shares * bid, 6))


class LiveExecutor:
    mode = "live"

    def __init__(self, clob_base: str = "https://clob.polymarket.com"):
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds

        key = os.environ["PM_PRIVATE_KEY"]
        funder = os.getenv("PM_FUNDER") or os.getenv("PM_ADDRESS") or None
        sig = int(os.getenv("PM_SIGNATURE_TYPE", "2"))
        self.client = ClobClient(
            host=clob_base, chain_id=137, key=key, signature_type=sig, funder=funder
        )
        k, s, p = os.getenv("PM_API_KEY"), os.getenv("PM_API_SECRET"), os.getenv("PM_API_PASSPHRASE")
        if k and s and p:
            self.client.set_api_creds(ApiCreds(api_key=k, api_secret=s, api_passphrase=p))
        else:
            self.client.set_api_creds(self.client.create_or_derive_api_creds())

    def _market_order(self, token_id: str, side: str, amount: float) -> Fill:
        from py_clob_client.clob_types import MarketOrderArgs, OrderType

        try:
            order = self.client.create_market_order(
                MarketOrderArgs(token_id=token_id, amount=amount, side=side)
            )
            resp = self.client.post_order(order, OrderType.FAK) or {}
            ok = bool(resp.get("success")) and str(resp.get("status", "")).lower() == "matched"
            taking = float(resp.get("takingAmount") or 0)
            making = float(resp.get("makingAmount") or 0)
            if side == "BUY":
                shares, usd = taking, making
            else:
                shares, usd = making, taking
            price = round(usd / shares, 6) if shares else 0.0
            return Fill(ok=ok, price=price, shares=shares, usd=usd,
                        order_id=resp.get("orderID"), raw=resp,
                        error=None if ok else str(resp.get("errorMsg") or resp.get("status")))
        except Exception as e:
            return Fill(ok=False, price=0.0, shares=0.0, usd=0.0, error=str(e))

    def buy(self, token_id: str, ask: float, stake_usd: float) -> Fill:
        return self._market_order(token_id, "BUY", stake_usd)

    def sell(self, token_id: str, bid: float, shares: float) -> Fill:
        return self._market_order(token_id, "SELL", shares)


def make_executor(execute: bool):
    return LiveExecutor() if execute else PaperExecutor()
