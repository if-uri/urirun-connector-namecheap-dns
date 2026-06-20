from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from urirun import v2
from urirun_connector_namecheap_dns import (
    apply,
    backup,
    connector_manifest,
    diff_records,
    normalize_records,
    plan,
    urirun_bindings,
)
from urirun_connector_namecheap_dns.cli import main


CURRENT = [{"Name": "@", "Type": "A", "Address": "203.0.113.10", "TTL": 1800}]
DESIRED = [{"Name": "@", "Type": "A", "Address": "203.0.113.11", "TTL": 1800}]


def _registry():
    return v2.compile_registry(urirun_bindings())


def test_manifest_and_bindings_shape() -> None:
    manifest = connector_manifest()
    bindings = urirun_bindings()
    routes = v2.list_routes(_registry())

    assert manifest["id"] == "namecheap-dns"
    assert "dns://host/records/command/plan" in manifest["routes"]
    assert bindings["version"] == "urirun.bindings.v2"
    assert "dns://host/records/command/apply" in bindings["bindings"]
    assert any(route["uri"] == "dns://host/records/command/backup" for route in routes)


def test_record_normalization_and_diff() -> None:
    current = normalize_records(CURRENT)
    desired = normalize_records(DESIRED)
    diff = diff_records(current, desired)

    assert current[0]["Type"] == "A"
    assert diff["changed"] is True
    assert diff["added"][0]["Address"] == "203.0.113.11"


def test_plan_backup_apply_mock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        planned = plan(domain="example.com", current_records=json.dumps(CURRENT), desired_records=json.dumps(DESIRED))
        assert planned["ok"] is True
        assert planned["requiresBackup"] is True

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


def test_cli_and_urirun_run_connector_uri(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "urirun-namecheap-dns"
        wrapper.write_text(
            f"#!/usr/bin/env sh\nexec {sys.executable} -m urirun_connector_namecheap_dns.cli \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        previous_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{previous_path}"
        try:
            assert main(["bindings"]) == 0
            bindings = json.loads(capsys.readouterr().out)
            assert "dns://host/records/command/plan" in bindings["bindings"]

            result = v2.run(
                "dns://host/records/command/plan",
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
        finally:
            os.environ["PATH"] = previous_path

