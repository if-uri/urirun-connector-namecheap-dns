# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import argparse
import sys

import urirun

from .core import connector_manifest, run_action, urirun_bindings




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


def register(sub) -> None:

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


def dispatch(args) -> int:
    data = vars(args)
    command = data.pop("command")
    try:
        result = run_action(command, **data)
    except Exception as exc:  # noqa: BLE001 - connector CLI reports JSON errors.
        urirun.connector_emit({"ok": False, "connector": "namecheap-dns", "action": command, "error": str(exc)})
        return 2
    urirun.connector_emit(result)
    return 0 if result.get("ok") else 2


def main(argv: list[str] | None = None) -> int:
    return urirun.connector_cli(
        "urirun-namecheap-dns",
        manifest=connector_manifest,
        bindings=urirun_bindings,
        register=register,
        dispatch=dispatch,
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
