# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Out-of-process executor for namecheap-dns routes.

The compiled v2 registry runs each route as an ``argv`` template that invokes
``python3 -m urirun_connector_namecheap_dns._exec <subcommand> ...``. urirun only
spawns this template under ``--execute``, so this module always runs the route
logic (via ``core.run_route``) and prints the connector's JSON result to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import core


def _bool_text(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _add_domain(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--domain", default="")


def _add_records(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current-records", default="")
    parser.add_argument("--mock-records", default="")
    parser.add_argument("--profile", default="")


def _add_expected(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-records", default="")
    parser.add_argument("--expected-a", default="")
    parser.add_argument("--expected-aaaa", default="")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="urirun_connector_namecheap_dns._exec")
    sub = parser.add_subparsers(dest="command", required=True)

    current = sub.add_parser("current", help="Read current Namecheap DNS records")
    _add_domain(current)
    _add_records(current)

    expected = sub.add_parser("expected", help="Render expected DNS records")
    _add_expected(expected)

    plan = sub.add_parser("plan", help="Plan Namecheap DNS changes")
    _add_domain(plan)
    _add_records(plan)
    plan.add_argument("--desired-records", default="")
    plan.add_argument("--ensure-records", default="")
    plan.add_argument("--remove-records", default="")

    backup = sub.add_parser("backup", help="Backup Namecheap DNS records")
    _add_domain(backup)
    _add_records(backup)
    backup.add_argument("--backup-dir", default="")

    apply = sub.add_parser("apply", help="Apply reviewed Namecheap DNS changes")
    _add_domain(apply)
    apply.add_argument("--current-records", default="")
    apply.add_argument("--desired-records", default="")
    apply.add_argument("--plan", default="")
    apply.add_argument("--backup-uri", default="")
    apply.add_argument("--confirm", type=_bool_text, default=False)
    apply.add_argument("--mock-apply", type=_bool_text, default=True)
    apply.add_argument("--allow-current-drift", type=_bool_text, default=False)
    apply.add_argument("--profile", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    kwargs = {k: v for k, v in vars(args).items() if k != "command"}
    try:
        result = core.run_route(args.command, **kwargs)
    except Exception as exc:  # noqa: BLE001 - connector exec reports JSON errors.
        print(json.dumps({"ok": False, "connector": core.CONNECTOR_ID, "action": args.command, "error": str(exc)}))
        return 2
    print(json.dumps(result))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
