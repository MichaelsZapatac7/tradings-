"""Calibration data recorder.

Runs with zero money at risk and builds the dataset that decides everything:
for each 5m slot it snapshots (seconds left, BTC lead, vol, model probability,
both order books) every few seconds, then records the actual resolution.

    python -m btc5m.record --hours 24

Output: runtime/calibration.jsonl
  {"type": "snap", "slug": ..., "sec_left": ..., "p_up": ..., "up_ask": ...}
  {"type": "outcome", "slug": ..., "resolved": "UP"|"DOWN"}
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import data, model


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(prog="btc5m.record")
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--poll-sec", type=float, default=4.0)
    args = ap.parse_args()

    out = Path(__file__).resolve().parents[1] / "runtime" / "calibration.jsonl"
    deadline = time.time() + args.hours * 3600
    pending: dict[str, float] = {}  # slug -> end_ts awaiting resolution
    print(f"[record] writing {out} for {args.hours}h")

    while time.time() < deadline or pending:
        # resolve finished slots
        for slug, end_ts in list(pending.items()):
            if time.time() >= end_ts + 10:
                res = data.market_resolution(slug)
                if res:
                    _append(out, {"type": "outcome", "ts": data.ts_utc(),
                                  "slug": slug, "resolved": res})
                    print(f"[record] {slug} resolved {res}")
                    del pending[slug]
                elif time.time() > end_ts + 300:
                    del pending[slug]  # give up

        if time.time() >= deadline:
            time.sleep(args.poll_sec)
            continue

        m = data.current_5m_market()
        if not m:
            time.sleep(args.poll_sec)
            continue
        pending.setdefault(m.slug, m.end_ts)

        snap: dict = {"type": "snap", "ts": data.ts_utc(), "slug": m.slug,
                      "sec_left": round(m.seconds_left, 1)}
        try:
            rows = data.kraken_1m_candles()
            fv = model.fair_value(m, rows)
            if fv:
                snap.update(p_up=round(fv.p_up, 4), lead=round(fv.lead, 2),
                            vol_1m=round(fv.vol_1m, 2))
            up_bid, up_ask, _, up_notional = data.order_book(m.up_token)
            dn_bid, dn_ask, _, dn_notional = data.order_book(m.down_token)
            snap.update(up_bid=up_bid, up_ask=up_ask, up_ask_notional=round(up_notional, 2),
                        dn_bid=dn_bid, dn_ask=dn_ask, dn_ask_notional=round(dn_notional, 2))
        except Exception as e:
            snap["error"] = str(e)
        _append(out, snap)
        time.sleep(args.poll_sec)

    print("[record] done")


if __name__ == "__main__":
    main()
