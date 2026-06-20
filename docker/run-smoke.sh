#!/usr/bin/env bash
set -euo pipefail

mkdir -p .docker-smoke

echo "==> direct connector CLI"
urirun-namecheap-dns plan \
  --domain example.com \
  --current-records '[{"Name":"@","Type":"A","Address":"203.0.113.10"}]' \
  --desired-records '[{"Name":"@","Type":"A","Address":"203.0.113.11"}]' > .docker-smoke/plan.json

urirun-namecheap-dns backup \
  --domain example.com \
  --current-records '[{"Name":"@","Type":"A","Address":"203.0.113.10"}]' \
  --backup-dir .docker-smoke/backups > .docker-smoke/backup.json

echo "==> build bindings and registry"
python3 - <<'PY' > .docker-smoke/bindings.json
import json
from urirun_connector_namecheap_dns import urirun_bindings
print(json.dumps(urirun_bindings(), indent=2))
PY

urirun validate .docker-smoke/bindings.json
urirun compile .docker-smoke/bindings.json --out .docker-smoke/registry.json

echo "==> execute connector URI through urirun"
urirun run 'dns://host/records/command/plan' .docker-smoke/registry.json \
  --payload '{"domain":"example.com","current_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]","desired_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.11\"}]"}' \
  --execute \
  --allow 'dns://host/*' > .docker-smoke/urirun-result.json

echo "==> project registry to MCP tools and A2A card"
python3 -m urirun.v2_mcp tools .docker-smoke/registry.json > .docker-smoke/mcp-tools.json
python3 -m urirun.v2_mcp card .docker-smoke/registry.json \
  --name namecheap-dns-docker \
  --url http://tester/ > .docker-smoke/a2a-card.json

python3 - <<'PY'
import json
from pathlib import Path

base = Path(".docker-smoke")
plan = json.loads((base / "plan.json").read_text())
backup = json.loads((base / "backup.json").read_text())
run = json.loads((base / "urirun-result.json").read_text())
run_payload = json.loads(run["result"]["stdout"])
tools = json.loads((base / "mcp-tools.json").read_text())
card = json.loads((base / "a2a-card.json").read_text())

assert plan["ok"] is True, plan
assert plan["diff"]["changed"] is True, plan
assert Path(backup["backup"]["path"]).exists(), backup
assert run["ok"] is True, run
assert run_payload["diff"]["changed"] is True, run_payload
assert any(tool["name"] == "dns_host_records_command_plan" for tool in tools["tools"]), tools
assert any("dns://host/records/command/plan" in skill.get("examples", []) for skill in card["skills"]), card
print(json.dumps({
    "ok": True,
    "mcpTools": len(tools["tools"]),
    "a2aSkills": len(card["skills"]),
}, indent=2))
PY

