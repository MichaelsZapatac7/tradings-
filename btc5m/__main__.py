import argparse
import dataclasses
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


def _from_profile(cls, profile: dict, overrides: dict):
    fields = {f.name for f in dataclasses.fields(cls)}
    kwargs = {k: v for k, v in profile.items() if k in fields}
    kwargs.update({k: v for k, v in overrides.items() if k in fields and v is not None})
    return cls(**kwargs)


def main() -> None:
    ap = argparse.ArgumentParser(prog="btc5m", description="BTC 5m Polymarket bot")
    ap.add_argument("--profile", default="fair_value",
                    help="profile from config/profiles.yaml (default: fair_value)")
    ap.add_argument("--stake-usd", type=float)
    ap.add_argument("--min-edge", type=float)
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--session-minutes", type=int)
    ap.add_argument("--exit-mode", choices=["hold", "before_close"])
    ap.add_argument("--execute", action="store_true",
                    help="LIVE trading with real money. Default is paper simulation.")
    args = ap.parse_args()

    p = load_profile(args.profile)
    overrides = {
        "stake_usd": args.stake_usd,
        "min_edge": args.min_edge,
        "threshold": args.threshold,
        "session_minutes": args.session_minutes,
        "exit_mode": args.exit_mode,
    }
    sp = _from_profile(StrategyParams, p, overrides)
    rp = _from_profile(RunnerParams, p, overrides)
    rp.execute = args.execute
    if rp.execute:
        print("*** LIVE MODE: real orders will be placed on Polymarket. ***")
    runtime = Path(__file__).resolve().parents[1] / "runtime"
    run_session(sp, rp, runtime)


if __name__ == "__main__":
    main()
