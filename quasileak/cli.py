import argparse
from importlib.metadata import version

from .evaluation_cli import add_commands as add_evaluation_commands


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="quasileak", description="QuasiLeak-Bench: evaluate privacy detectors and construct evidence groups."
    )
    parser.add_argument("--version", action="version", version="QuasiLeak-Bench " + version("quasileak-bench"))
    commands = parser.add_subparsers(dest="command", required=True)
    add_evaluation_commands(commands)
    # Preserve the existing construction commands and their interfaces.
    from .construction_cli import add_commands, run
    add_commands(commands)
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "handler"):
            return args.handler(args) or 0
        return run(args)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc!s}\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nInterrupted. Use --resume to continue a model run.\n")


if __name__ == "__main__":
    raise SystemExit(main())
