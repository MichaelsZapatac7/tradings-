"""Evaluate recorded calibration data: is there a measurable edge?

    python -m btc5m.evaluate

Reports:
- Model calibration (Brier score) vs. the market's own implied probability.
  If the model does not beat the market mid, there is no edge — stop there.
- Hypothetical PnL of the fair-value rule at several min_edge levels
  (buy at observed ask, settle at actual resolution), with trade counts.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ENTRY_WINDOW = (60, 150)   # sec_left window used for hypothetical trades
EDGES = [0.03, 0.05, 0.08, 0.10, 0.15]


def load(path: Path):
    snaps, outcomes = defaultdict(list), {}
    with path.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("type") == "snap":
                snaps[r["slug"]].append(r)
            elif r.get("type") == "outcome":
                outcomes[r["slug"]] = r["resolved"]
    return snaps, outcomes


def main() -> None:
    ap = argparse.ArgumentParser(prog="btc5m.evaluate")
    ap.add_argument("--file", default=None)
    args = ap.parse_args()
    path = Path(args.file) if args.file else \
        Path(__file__).resolve().parents[1] / "runtime" / "calibration.jsonl"
    if not path.exists():
        raise SystemExit(f"no data at {path}; run `python -m btc5m.record` first")

    snaps, outcomes = load(path)
    resolved = {s: o for s, o in outcomes.items() if s in snaps}
    print(f"slots with snapshots: {len(snaps)}, resolved: {len(resolved)}")
    if not resolved:
        return

    # --- calibration: model vs market, on snapshots inside the entry window
    n = 0
    brier_model = brier_market = 0.0
    for slug, res in resolved.items():
        y = 1.0 if res == "UP" else 0.0
        for s in snaps[slug]:
            if s.get("p_up") is None or s.get("up_bid") is None or s.get("up_ask") is None:
                continue
            if not (ENTRY_WINDOW[0] <= s["sec_left"] <= ENTRY_WINDOW[1]):
                continue
            mid = (s["up_bid"] + s["up_ask"]) / 2
            brier_model += (s["p_up"] - y) ** 2
            brier_market += (mid - y) ** 2
            n += 1
    if n:
        print(f"\ncalibration on {n} in-window snapshots:")
        print(f"  Brier model : {brier_model / n:.4f}")
        print(f"  Brier market: {brier_market / n:.4f}"
              f"  ({'model BEATS market' if brier_model < brier_market else 'model does NOT beat market — no edge'})")

    # --- hypothetical PnL per min_edge (first qualifying snapshot per slot)
    print("\nhypothetical PnL per $1 stake, settle at resolution:")
    print(f"{'min_edge':>8} {'trades':>7} {'wins':>5} {'total_pnl':>10} {'avg/trade':>10}")
    for e in EDGES:
        trades = wins = 0
        pnl = 0.0
        for slug, res in resolved.items():
            for s in sorted(snaps[slug], key=lambda x: -x["sec_left"]):
                if s.get("p_up") is None:
                    continue
                if not (ENTRY_WINDOW[0] <= s["sec_left"] <= ENTRY_WINDOW[1]):
                    continue
                for side, ask_k, p in (("UP", "up_ask", s["p_up"]),
                                       ("DOWN", "dn_ask", 1 - s["p_up"])):
                    ask = s.get(ask_k)
                    if ask is None or ask <= 0 or ask > 0.97:
                        continue
                    if p - ask < e:
                        continue
                    won = (res == side)
                    shares = 1.0 / ask
                    pnl += (shares * 1.0 - 1.0) if won else -1.0
                    trades += 1
                    wins += 1 if won else 0
                    break
                else:
                    continue
                break  # one trade per slot
        avg = pnl / trades if trades else 0.0
        print(f"{e:>8.2f} {trades:>7} {wins:>5} {pnl:>10.3f} {avg:>10.3f}")

    print("\nNOTE: needs hundreds of resolved slots (days of recording) before "
          "these numbers mean anything.")


if __name__ == "__main__":
    main()
