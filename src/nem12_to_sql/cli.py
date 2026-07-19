import argparse
import logging
import sys
from pathlib import Path

from nem12_to_sql.exceptions import NEM12ParseError
from nem12_to_sql.parser import NEM12Parser

logger = logging.getLogger("nem12_to_sql")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nem12-to-sql",
        description="Convert a NEM12 meter data file into batched INSERT statements for meter_readings.",
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the NEM12 input csv formatted file",
    )
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="Log and skip malformed 300 records instead of aborting the whole file",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    parser = NEM12Parser(lenient=args.lenient)

    try:
        with args.input_file.open("r", encoding="utf-8", newline="") as in_stream:
            readings = list(parser.parse(in_stream))
            print(len(readings))
            for reading in readings[:10]:
                print(reading)
    except FileNotFoundError:
        logger.error("input file not found: %s", args.input_file)
        return 1
    except NEM12ParseError as exc:
        logger.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
