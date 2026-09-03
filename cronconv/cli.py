import argparse
import sys
from typing import List, Optional

from .convert import parse_quartz, parse_standard, to_quartz, to_standard
from .errors import CronFormatError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cronconv",
        description="Convert cron expressions between standard 5-field and Quartz 6/7-field syntax.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    to_q = sub.add_parser("to-quartz", help="convert a standard cron expression to quartz syntax")
    to_q.add_argument("expression", help="e.g. '*/15 9-17 * * MON-FRI'")
    to_q.add_argument(
        "--lenient",
        action="store_true",
        help="accept non-standard input and make a best-effort, possibly lossy conversion",
    )

    to_s = sub.add_parser("to-standard", help="convert a quartz cron expression to standard syntax")
    to_s.add_argument("expression", help="e.g. '0 0 12 ? * MON-FRI'")
    to_s.add_argument(
        "--lenient",
        action="store_true",
        help="drop fields standard cron cannot represent (seconds, year) instead of raising",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "to-quartz":
            standard = parse_standard(args.expression, lenient=args.lenient)
            print(to_quartz(standard, lenient=args.lenient))
        elif args.command == "to-standard":
            quartz = parse_quartz(args.expression, lenient=args.lenient)
            print(to_standard(quartz, lenient=args.lenient))
    except CronFormatError as exc:
        print(f"cronconv: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
