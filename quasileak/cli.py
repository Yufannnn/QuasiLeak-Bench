import argparse
import sys
from importlib.metadata import version

from .evaluation_cli import add_commands as add_evaluation_commands
from . import terminal


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="quasileak", description="QuasiLeak-Bench: evaluate privacy detectors and construct evidence groups."
    )
    parser.add_argument("--version", action="version", version="QuasiLeak-Bench " + version("quasileak-bench"))
    parser.add_argument("--plain", action="store_true", help="Disable terminal decoration (JSON/CSV are always plain)")
    commands = parser.add_subparsers(dest="command", required=True)
    banner = commands.add_parser("banner", help="Show the terminal wordmark and release badges")
    banner.add_argument("--demo", action="store_true", help="Label a synthetic offline demonstration")
    banner.set_defaults(handler=lambda args: terminal.banner(demo=args.demo))
    add_evaluation_commands(commands)
    # Preserve the existing construction commands and their interfaces.
    from .construction_cli import add_commands, run
    add_commands(commands)
    arguments = list(argv) if argv is not None else sys.argv[1:]
    terminal.configure(plain="--plain" in arguments)
    if not arguments or arguments == ["--help"]:
        if terminal.enabled():
            terminal.banner()
        if not arguments:
            parser.print_help()
            return 0
    args = parser.parse_args(arguments)
    terminal.configure(plain=args.plain)
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
