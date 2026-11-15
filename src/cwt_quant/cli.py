"""Command-line entry point with robust error handling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config
from .exceptions import CWTQuantError, ConfigError, DataError
from .logging_utils import setup_logging, get_logger
from .pipeline import run_pipeline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="CWT Quant — leakage-safe daily equity + sentiment research pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--ticker", default="AAPL", help="Equity ticker")
    parser.add_argument("--out", default="outputs", help="Output directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-influence",
        action="store_true",
        help="Disable influence experiment even if coverage gate passes",
    )
    parser.add_argument(
        "--real-data",
        action="store_true",
        help="Use real prices (yfinance) + free StockTwits/news/CWT sentiment proxies",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=180,
        help="Calendar days of history for real-data mode",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--min-train",
        type=int,
        default=None,
        help="Override min_train_sessions",
    )
    parser.add_argument(
        "--allow-missing-sessions",
        action="store_true",
        help="Do not fail hard on missing price sessions (audit only)",
    )
    args = parser.parse_args(argv)

    setup_logging(args.log_level)
    log = get_logger("cwt_quant.cli")

    try:
        cfg = Config(
            ticker=args.ticker.upper(),
            seed=args.seed,
            outputs_dir=Path(args.out),
            enable_influence=not args.no_influence,
            real_data_present=args.real_data,
            history_calendar_days=args.history_days,
            log_level=args.log_level,
            fail_on_missing_sessions=not args.allow_missing_sessions,
            min_train_sessions=args.min_train or 40,
        )
        cfg.validate()
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 2

    log.info("CWT Quant — experimental reference run")
    log.info("  ticker=%s  seed=%s  influence=%s", cfg.ticker, cfg.seed, cfg.enable_influence)

    try:
        result = run_pipeline(
            cfg,
            force_synthetic=not args.real_data,
            out_dir=Path(args.out),
        )
    except DataError as exc:
        log.error("Data error: %s", exc)
        return 3
    except CWTQuantError as exc:
        log.error("Pipeline error: %s", exc)
        return 4
    except NotImplementedError as exc:
        log.error("Not implemented: %s", exc)
        return 5
    except Exception as exc:
        log.exception("Unexpected failure: %s", exc)
        return 1

    print(f"\nReport: {result['report_path']}")
    print(f"Influence experiment active: {result['influence_enabled']}")
    print(
        f"Sessions: {result['meta'].get('n_sessions')}  "
        f"Posts: {result['meta'].get('n_posts')}"
    )
    if result.get("warnings"):
        print(f"Warnings: {len(result['warnings'])}")
    print("Status: EXPERIMENTAL — no predictive skill claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
