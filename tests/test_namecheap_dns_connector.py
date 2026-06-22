# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from urirun import v2
from urirun_connector_namecheap_dns import (
    apply,
    backup,
    connector_manifest,
    diff_records,
    main,
    normalize_records,
    plan,
    run_route,
    urirun_bindings,
)
from urirun_connector_namecheap_dns import _exec


ROUTE_PLAN = "dns://host/records/command/plan"
ROUTE_BACKUP = "dns://host/records/command/backup"
ROUTE_APPLY = "dns://host/records/command/apply"
ROUTE_CURRENT = "dns://host/records/query/current"
ROUTE_EXPECTED = "dns://host/records/query/expected"
ALL_ROUTES = {ROUTE_PLAN, ROUTE_BACKUP, ROUTE_APPLY, ROUTE_CURRENT, ROUTE_EXPECTED}

CURRENT = [{"Name": "@", "Type": "A", "Address": "203.0.113.10", "TTL": 1800}]
DESIRED = [{"Name": "@", "Type": "A", "Address": "203.0.113.11", "TTL": 1800}]


def _registry():
    return v2.compile_registry(urirun_bindings())


def test_bindings_are_argv_template_via_exec() -> None:
    route = urirun_bindings()["bindings"][ROUTE_PLAN]
    assert route["adapter"] == "argv-template"
    assert route["argv"][:5] == [
        "python3", "-m", "urirun_connector_namecheap_dns._exec", "plan", "--domain",
    ]
    json.dumps(urirun_bindings())  # serializable


def test_compiles_and_routes_present() -> None:
    routes = {r["uri"] for r in v2.list_routes(_registry())}
    assert ALL_ROUTES <= routes


def test_manifest_prose_plus_derived_routes() -> None:
    manifest = connector_manifest()
    assert manifest["id"] == "namecheap-dns"
    assert set(manifest["routes"]) == ALL_ROUTES
    assert manifest["uriSchemes"] == ["dns"]
    assert manifest["summary"]  # prose preserved


def test_record_normalization_and_diff() -> None:
    current = normalize_records(CURRENT)
    desired = normalize_records(DESIRED)
    diff = diff_records(current, desired)

    assert current[0]["Type"] == "A"
    assert diff["changed"] is True
    assert diff["added"][0]["Address"] == "203.0.113.11"


def test_offline_plan_backup_apply_return_dicts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        planned = plan(domain="example.com", current_records=json.dumps(CURRENT), desired_records=json.dumps(DESIRED))
        assert planned["ok"] is True
        assert planned["requiresBackup"] is True
        assert planned["diff"]["changed"] is True

        backed_up = backup(domain="example.com", current_records=json.dumps(CURRENT), backup_dir=str(Path(tmp) / "backups"))
        assert backed_up["ok"] is True
        assert Path(backed_up["backup"]["path"]).exists()

        applied = apply(
            domain="example.com",
            current_records=json.dumps(CURRENT),
            plan=json.dumps(planned),
            backup_uri=backed_up["backup"]["uri"],
            confirm=True,
            mock_apply=True,
        )
        assert applied["ok"] is True
        assert applied["mock"] is True


def test_run_route_dispatch_offline() -> None:
    result = run_route(
        "plan",
        domain="example.com",
        current_records=json.dumps(CURRENT),
        desired_records=json.dumps(DESIRED),
    )
    assert result["ok"] is True
    assert result["action"] == "plan"


def test_no_real_api_call_on_offline_routes(monkeypatch) -> None:
    from urirun_connector_namecheap_dns import core

    def _boom(*_args, **_kwargs):
        raise AssertionError("real Namecheap API must not be called offline")

    monkeypatch.setattr(core, "request_api", _boom)
    result = run_route("expected", expected_a="203.0.113.10")
    assert result["ok"] is True
    assert result["expectedRecords"]["A"] == ["203.0.113.10"]


def test_exec_emits_json_for_offline_route(capsys) -> None:
    rc = _exec.main([
        "plan",
        "--domain", "example.com",
        "--current-records", json.dumps(CURRENT),
        "--desired-records", json.dumps(DESIRED),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["diff"]["changed"] is True


def test_cli_bindings_and_manifest(capsys) -> None:
    assert main(["bindings"]) == 0
    assert ROUTE_PLAN in json.loads(capsys.readouterr().out)["bindings"]
    assert main(["manifest"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "namecheap-dns"


def test_compiled_registry_run_offline_plan() -> None:
    result = v2.run(
        ROUTE_PLAN,
        _registry(),
        {
            "domain": "example.com",
            "current_records": json.dumps(CURRENT),
            "desired_records": json.dumps(DESIRED),
        },
        mode="execute",
        policy={"execute": {"allow": ["dns://host/*"]}},
    )
    assert result["ok"] is True, result
    stdout = json.loads(result["result"]["stdout"])
    assert stdout["diff"]["changed"] is True
