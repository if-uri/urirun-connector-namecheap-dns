# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import urirun
from urirun import v2
from urirun_connector_namecheap_dns import (
    apply,
    apply_route,
    backup,
    backup_route,
    connector_manifest,
    current_route,
    diff_records,
    expected_route,
    main,
    normalize_records,
    plan,
    plan_route,
    urirun_bindings,
)

ROUTE_PLAN = "dns://host/records/command/plan"
ROUTE_BACKUP = "dns://host/records/command/backup"
ROUTE_APPLY = "dns://host/records/command/apply"
ROUTE_CURRENT = "dns://host/records/query/current"
ROUTE_EXPECTED = "dns://host/records/query/expected"
ALL_ROUTES = {ROUTE_PLAN, ROUTE_BACKUP, ROUTE_APPLY, ROUTE_CURRENT, ROUTE_EXPECTED}

CURRENT = [{"Name": "@", "Type": "A", "Address": "203.0.113.10", "TTL": 1800}]
DESIRED = [{"Name": "@", "Type": "A", "Address": "203.0.113.11", "TTL": 1800}]

MODULE = "urirun_connector_namecheap_dns.core"


# --- real impl functions called directly (offline) -------------------------

def test_config_from_env_resolves_api_key_secret_reference(monkeypatch) -> None:
    from urirun_connector_namecheap_dns import core

    monkeypatch.setenv("NC_REAL_KEY", "live-api-key-xyz")
    base = {
        "NAMECHEAP_API_USER": "user", "NAMECHEAP_USERNAME": "user",
        "NAMECHEAP_CLIENT_IP": "203.0.113.5",
    }

    # The env var holds a reference, not the key -> resolved via the secrets layer.
    cfg = core.config_from_env(env={**base, "NAMECHEAP_API_KEY": "getv://NC_REAL_KEY"})
    assert cfg["api_key"] == "live-api-key-xyz"

    # A literal key still passes straight through (backward compatible).
    cfg2 = core.config_from_env(env={**base, "NAMECHEAP_API_KEY": "literal-key"})
    assert cfg2["api_key"] == "literal-key"

    # An explicit allow-list that excludes the reference denies it (deny-by-default).
    import pytest
    with pytest.raises(ValueError, match="denied by policy"):
        core.config_from_env(env={
            **base, "NAMECHEAP_API_KEY": "getv://NC_REAL_KEY",
            "NAMECHEAP_SECRET_ALLOW": "getv://SOMETHING_ELSE",
        })


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


def test_handlers_offline(monkeypatch) -> None:
    # Handlers must compute from payload mock/supplied records, never the API.
    from urirun_connector_namecheap_dns import core

    def _boom(*_args, **_kwargs):
        raise AssertionError("real Namecheap API must not be called offline")

    monkeypatch.setattr(core, "request_api", _boom)

    plan_result = plan_route(
        domain="example.com",
        current_records=json.dumps(CURRENT),
        desired_records=json.dumps(DESIRED),
    )
    assert plan_result["ok"] is True
    assert plan_result["action"] == "plan"
    assert plan_result["diff"]["changed"] is True

    expected_result = expected_route(expected_a="203.0.113.10")
    assert expected_result["ok"] is True
    assert expected_result["expectedRecords"]["A"] == ["203.0.113.10"]

    current_result = current_route(mock_records=json.dumps(CURRENT))
    assert current_result["ok"] is True
    assert current_result["action"] == "current"
    assert current_result["records"][0]["Address"] == "203.0.113.10"


# --- v2 authoring contract: isolated handlers (registry-portable) ----------

def test_bindings_are_isolated_handlers() -> None:
    b = urirun_bindings()["bindings"]
    assert set(b) == ALL_ROUTES
    for route, export in (
        (ROUTE_CURRENT, "current_route"),
        (ROUTE_EXPECTED, "expected_route"),
        (ROUTE_PLAN, "plan_route"),
        (ROUTE_BACKUP, "backup_route"),
        (ROUTE_APPLY, "apply_route"),
    ):
        # registry-portable in-process handler: runs out-of-process via urirun.exec
        assert b[route]["adapter"] == "local-function-subprocess"
        assert b[route]["python"]["module"] == MODULE
        assert b[route]["python"]["export"] == export
        assert "argv" not in b[route]
    plan_props = b[ROUTE_PLAN]["inputSchema"]["properties"]
    assert {"domain", "current_records", "desired_records", "ensure_records", "remove_records", "mock_records", "profile"} <= set(plan_props)
    json.dumps(urirun_bindings())  # serializable: no live ref leaks


def test_compiles_and_routes_present() -> None:
    registry = urirun.compile_registry(urirun_bindings())
    uris = {r["uri"] for r in urirun.list_routes(registry)}
    assert ALL_ROUTES <= uris


def test_runtime_executes_from_compiled_registry() -> None:
    # the whole point: a serialized->compiled registry still runs the offline route
    registry = urirun.compile_registry(json.loads(json.dumps(urirun_bindings())))
    policy = urirun.policy(allow=["dns://*"])

    env = v2.run(
        ROUTE_PLAN,
        registry,
        payload={
            "domain": "example.com",
            "current_records": json.dumps(CURRENT),
            "desired_records": json.dumps(DESIRED),
        },
        mode="execute",
        policy=policy,
    )
    assert env["ok"] is True, env
    data = urirun.result_data(env)
    assert data["ok"] is True
    assert data["diff"]["changed"] is True


def test_manifest_prose_plus_derived_routes() -> None:
    m = connector_manifest()
    assert m["id"] == "namecheap-dns"
    assert set(m["routes"]) == ALL_ROUTES
    assert m["uriSchemes"] == ["dns"]
    assert m["summary"]  # prose preserved
    assert m["install"]["mode"] == "urirun-extra"
    json.dumps(m)


# --- CLI -------------------------------------------------------------------

def test_cli_bindings_and_manifest(capsys) -> None:
    assert main(["bindings"]) == 0
    assert ROUTE_PLAN in json.loads(capsys.readouterr().out)["bindings"]
    assert main(["manifest"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "namecheap-dns"
