import argparse

from .construction_cli import add_commands, run


def main() -> int:
    parser = argparse.ArgumentParser(prog="quasileak")
    add_commands(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args()
    try:
        return run(args)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc!s}\n")


if __name__ == "__main__":
    raise SystemExit(main())
