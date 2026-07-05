import argparse
from pathlib import Path

import yaml

from .runner import RunnerParams, run_session
from .strategy import StrategyParams


def load_profile(name: str) -> dict:
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "profiles.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    profiles = cfg.get("profiles", {})
    if name not in profiles:
        raise SystemExit(f"unknown profile '{name}' (available: {', '.join(profiles)})")
    return profiles[name]


def main() -> None:
    ap = argparse.ArgumentParser(prog="btc5m", description="BTC 5m Polymarket momentum bot")
    ap.add_argument("--profile", default="conservative")
    ap.add_argument("--stake-usd", type=float)
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--session-minutes", type=int)
    ap.add_argument("--exit-mode", choices=["hold", "before_close"])
    ap.add_argument("--no-btc-move-filter", action="store_true",
                    help="disable the BTC impulse confirmation (replicates original Novals83 behavior)")
    ap.add_argument("--execute", action="store_true",
                    help="LIVE trading with real money. Default is paper simulation.")
    args = ap.parse_args()

    p = load_profile(args.profile)
    sp = StrategyParams(
        threshold=args.threshold or p["threshold"],
        min_entry_seconds_left=p["min_entry_seconds_left"],
        max_entry_seconds_left=p["max_entry_seconds_left"],
        btc_move_min_usd=p["btc_move_min_usd"],
        require_btc_move=not args.no_btc_move_filter and p.get("require_btc_move", True),
        max_spread=p["max_spread"],
        min_top_ask_notional_usd=p["min_top_ask_notional_usd"],
    )
    rp = RunnerParams(
        stake_usd=args.stake_usd or p["stake_usd"],
        stop_loss_pct=p["stop_loss_pct"],
        exit_mode=args.exit_mode or p.get("exit_mode", "hold"),
        exit_before_sec=p.get("exit_before_sec", 20),
        session_minutes=args.session_minutes or p.get("session_minutes", 60),
        daily_max_loss_usd=p["daily_max_loss_usd"],
        max_trades_per_day=p["max_trades_per_day"],
        execute=args.execute,
    )
    if rp.execute:
        print("*** LIVE MODE: real orders will be placed on Polymarket. ***")
    runtime = Path(__file__).resolve().parents[1] / "runtime"
    run_session(sp, rp, runtime)


if __name__ == "__main__":
    main()
