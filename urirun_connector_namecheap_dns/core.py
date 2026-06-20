# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import urirun


CONNECTOR_ID = "namecheap-dns"
DNS = urirun.connector(CONNECTOR_ID, scheme="dns")

API_TIMEOUT_SECONDS = 30
API_PROD = "https://api.namecheap.com/xml.response"
API_SANDBOX = "https://api.sandbox.namecheap.com/xml.response"
SUPPORTED_RECORD_KEYS = ("Name", "Type", "Address", "TTL", "MXPref", "EmailType", "Flag", "Tag")


def connector_manifest() -> dict[str, Any]:
    return urirun.load_manifest(__package__)


def _json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def _bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return sorted({str(item) for item in value if str(item)})
    return sorted({item.strip() for item in str(value).split(",") if item.strip()})


def now_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def split_domain(domain: str) -> tuple[str, str]:
    if "." not in domain:
        raise ValueError(f"domain must include a TLD: {domain}")
    sld, tld = domain.rsplit(".", 1)
    return sld, tld


def env_name(profile: str | None, name: str) -> str:
    if profile:
        return f"NAMECHEAP_{profile.upper()}_{name}"
    return f"NAMECHEAP_{name}"


def config_from_env(profile: str | None = None, env: dict | None = None) -> dict[str, Any]:
    env = env or os.environ
    sandbox = env.get(env_name(profile, "SANDBOX"), env.get("NAMECHEAP_SANDBOX", "false")).lower() in {"1", "true", "yes", "on"}
    config = {
        "api_user": env.get(env_name(profile, "API_USER")) or env.get("NAMECHEAP_API_USER"),
        "api_key": env.get(env_name(profile, "API_KEY")) or env.get("NAMECHEAP_API_KEY"),
        "username": env.get(env_name(profile, "USERNAME")) or env.get("NAMECHEAP_USERNAME"),
        "client_ip": env.get(env_name(profile, "CLIENT_IP")) or env.get("NAMECHEAP_CLIENT_IP"),
        "sandbox": sandbox,
        "endpoint": env.get(env_name(profile, "ENDPOINT")) or env.get("NAMECHEAP_ENDPOINT") or (API_SANDBOX if sandbox else API_PROD),
        "profile": profile,
    }
    missing = [key for key in ("api_user", "api_key", "username", "client_ip") if not config.get(key)]
    if missing:
        raise ValueError(f"missing Namecheap env keys: {', '.join(missing)}")
    return config


def auth_params(config: dict[str, Any], command: str, domain: str) -> dict[str, str]:
    sld, tld = split_domain(domain)
    return {
        "ApiUser": str(config["api_user"]),
        "ApiKey": str(config["api_key"]),
        "UserName": str(config["username"]),
        "ClientIp": str(config["client_ip"]),
        "Command": command,
        "SLD": sld,
        "TLD": tld,
    }


def request_api(config: dict[str, Any], command: str, domain: str, params: dict | None = None, method: str = "GET") -> str:
    body = {**auth_params(config, command, domain), **(params or {})}
    encoded = urllib.parse.urlencode(body).encode("utf-8")
    if method.upper() == "POST":
        request = urllib.request.Request(config["endpoint"], data=encoded, method="POST")
    else:
        request = urllib.request.Request(f"{config['endpoint']}?{encoded.decode('utf-8')}", method="GET")
    with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_api_xml(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    status = root.attrib.get("Status")
    errors = []
    hosts = []
    set_success = None
    for elem in root.iter():
        name = _strip_ns(elem.tag)
        if name == "Error":
            errors.append({"number": elem.attrib.get("Number"), "message": (elem.text or "").strip()})
        elif name.lower() == "host":
            hosts.append(
                normalize_record(
                    {
                        "Name": elem.attrib.get("Name", "@"),
                        "Type": elem.attrib.get("Type", ""),
                        "Address": elem.attrib.get("Address", ""),
                        "TTL": elem.attrib.get("TTL"),
                        "MXPref": elem.attrib.get("MXPref"),
                    }
                )
            )
        elif name == "DomainDNSSetHostsResult":
            set_success = elem.attrib.get("IsSuccess", "").lower() == "true"
    ok = status == "OK" and not errors
    return {"ok": ok, "status": status, "errors": errors, "records": hosts, "setSuccess": set_success}


def normalize_record(record: dict[str, Any]) -> dict[str, str]:
    output = {
        "Name": str(record.get("Name") or record.get("name") or "@"),
        "Type": str(record.get("Type") or record.get("type") or "").upper(),
        "Address": str(record.get("Address") or record.get("address") or ""),
    }
    ttl = record.get("TTL", record.get("ttl"))
    mxpref = record.get("MXPref", record.get("mxpref", record.get("mx_pref")))
    if ttl not in (None, ""):
        output["TTL"] = str(ttl)
    if mxpref not in (None, ""):
        output["MXPref"] = str(mxpref)
    for key in ("EmailType", "Flag", "Tag"):
        value = record.get(key, record.get(key.lower()))
        if value not in (None, ""):
            output[key] = str(value)
    if not output["Type"] or not output["Address"]:
        raise ValueError(f"record requires Type and Address: {record}")
    return output


def record_key(record: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(record.get("Name", "@")),
        str(record.get("Type", "")),
        str(record.get("Address", "")),
        str(record.get("MXPref", "")),
        str(record.get("TTL", "")),
        str(record.get("EmailType", "")),
        str(record.get("Flag", "")),
        str(record.get("Tag", "")),
    )


def normalize_records(records: Any) -> list[dict[str, str]]:
    parsed = _json_value(records, []) if not isinstance(records, list) else records
    return sorted((normalize_record(record) for record in (parsed or [])), key=record_key)


def record_identity(record: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(record.get("Name", "@")),
        str(record.get("Type", "")),
        str(record.get("Address", "")),
        str(record.get("MXPref", "")),
    )


def merge_records(current: Any, ensure: Any = None, remove: Any = None) -> list[dict[str, str]]:
    records = {record_identity(record): record for record in normalize_records(current)}
    for record in normalize_records(remove):
        records.pop(record_identity(record), None)
    for record in normalize_records(ensure):
        records[record_identity(record)] = record
    return sorted(records.values(), key=record_key)


def diff_records(current: Any, desired: Any) -> dict[str, Any]:
    current_map = {record_key(record): record for record in normalize_records(current)}
    desired_map = {record_key(record): record for record in normalize_records(desired)}
    added = [desired_map[key] for key in sorted(desired_map.keys() - current_map.keys())]
    removed = [current_map[key] for key in sorted(current_map.keys() - desired_map.keys())]
    return {"changed": bool(added or removed), "added": added, "removed": removed}


def expected_records(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> dict[str, list[str]]:
    expected = _json_value(expected_records, {}) if expected_records else {}
    if not isinstance(expected, dict):
        expected = {"A": _list(expected)}
    if expected_a:
        expected["A"] = _list(expected_a)
    if expected_aaaa:
        expected["AAAA"] = _list(expected_aaaa)
    return {str(key).upper(): _list(value) for key, value in expected.items() if _list(value)}


def desired_from_payload(current: list[dict[str, str]], payload: dict[str, Any]) -> list[dict[str, str]]:
    if payload.get("desired_records") not in (None, ""):
        return normalize_records(payload.get("desired_records"))
    return merge_records(current, ensure=payload.get("ensure_records"), remove=payload.get("remove_records"))


def _records_payload(
    *,
    current_records: str = "",
    mock_records: str = "",
    desired_records: str = "",
    ensure_records: str = "",
    remove_records: str = "",
    plan: str = "",
    backup_uri: str = "",
    confirm: bool | str = False,
    mock_apply: bool | str = False,
    allow_current_drift: bool | str = False,
    profile: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if current_records:
        payload["current_records"] = _json_value(current_records, [])
    if mock_records:
        payload["mock_records"] = _json_value(mock_records, [])
    if desired_records:
        payload["desired_records"] = _json_value(desired_records, [])
    if ensure_records:
        payload["ensure_records"] = _json_value(ensure_records, [])
    if remove_records:
        payload["remove_records"] = _json_value(remove_records, [])
    if plan:
        payload["plan"] = _json_value(plan, {})
    if backup_uri:
        payload["backup_uri"] = backup_uri
    if profile:
        payload["profile"] = profile
    payload["confirm"] = _bool(confirm)
    payload["mock_apply"] = _bool(mock_apply)
    payload["allow_current_drift"] = _bool(allow_current_drift)
    return payload


def current_records(domain: str = "", current_records: str = "", mock_records: str = "", profile: str = "") -> list[dict[str, str]]:
    payload = _records_payload(current_records=current_records, mock_records=mock_records, profile=profile)
    if payload.get("current_records") is not None:
        return normalize_records(payload.get("current_records"))
    if payload.get("mock_records") is not None:
        return normalize_records(payload.get("mock_records"))
    config = config_from_env(payload.get("profile"))
    response = request_api(config, "namecheap.domains.dns.getHosts", domain)
    parsed = parse_api_xml(response)
    if not parsed["ok"]:
        raise ValueError(f"Namecheap getHosts failed: {parsed['errors']}")
    return normalize_records(parsed["records"])


def plan(
    domain: str = "",
    current_records: str = "",
    desired_records: str = "",
    ensure_records: str = "",
    remove_records: str = "",
    mock_records: str = "",
    profile: str = "",
) -> dict[str, Any]:
    payload = _records_payload(
        current_records=current_records,
        mock_records=mock_records,
        desired_records=desired_records,
        ensure_records=ensure_records,
        remove_records=remove_records,
        profile=profile,
    )
    current = normalize_records(payload.get("current_records")) if payload.get("current_records") is not None else current_records_fn(domain, payload)
    desired = desired_from_payload(current, payload)
    diff = diff_records(current, desired)
    return {
        "ok": True,
        "connector": CONNECTOR_ID,
        "type": "namecheap-dns",
        "action": "plan",
        "domain": domain,
        "currentRecords": current,
        "desiredRecords": desired,
        "diff": diff,
        "requiresBackup": True,
        "requiresConfirm": True,
        "destructive": bool(diff["removed"]),
    }


def current_records_fn(domain: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    if payload.get("current_records") is not None:
        return normalize_records(payload.get("current_records"))
    if payload.get("mock_records") is not None:
        return normalize_records(payload.get("mock_records"))
    config = config_from_env(payload.get("profile"))
    response = request_api(config, "namecheap.domains.dns.getHosts", domain)
    parsed = parse_api_xml(response)
    if not parsed["ok"]:
        raise ValueError(f"Namecheap getHosts failed: {parsed['errors']}")
    return normalize_records(parsed["records"])


def sethosts_params(records: Any) -> dict[str, str]:
    params: dict[str, str] = {}
    for index, record in enumerate(normalize_records(records), start=1):
        params[f"HostName{index}"] = record["Name"]
        params[f"RecordType{index}"] = record["Type"]
        params[f"Address{index}"] = record["Address"]
        for key in SUPPORTED_RECORD_KEYS:
            if key in {"Name", "Type", "Address"}:
                continue
            if record.get(key) not in (None, ""):
                prefix = "MXPref" if key == "MXPref" else key
                params[f"{prefix}{index}"] = str(record[key])
    return params


def backup(domain: str = "", current_records: str = "", mock_records: str = "", backup_dir: str = "", profile: str = "") -> dict[str, Any]:
    payload = _records_payload(current_records=current_records, mock_records=mock_records, profile=profile)
    records = current_records_fn(domain, payload)
    timestamp = now_id()
    directory = Path(backup_dir or "~/.urirun/artifacts/namecheap").expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{domain}-{timestamp}.dns-backup.json"
    content = {"domain": domain, "records": normalize_records(records), "createdAt": timestamp, "provider": "namecheap"}
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact = {
        "kind": "dns-backup",
        "uri": f"artifact://host/namecheap/dns-backup/{domain}/{timestamp}",
        "path": str(path),
        "meta": content,
    }
    return {"ok": True, "connector": CONNECTOR_ID, "type": "namecheap-dns", "action": "backup", "domain": domain, "backup": artifact}


def apply(
    domain: str = "",
    current_records: str = "",
    desired_records: str = "",
    plan: str = "",
    backup_uri: str = "",
    confirm: bool | str = False,
    mock_apply: bool | str = True,
    allow_current_drift: bool | str = False,
    profile: str = "",
) -> dict[str, Any]:
    payload = _records_payload(
        current_records=current_records,
        desired_records=desired_records,
        plan=plan,
        backup_uri=backup_uri,
        confirm=confirm,
        mock_apply=mock_apply,
        allow_current_drift=allow_current_drift,
        profile=profile,
    )
    if payload.get("confirm") is not True:
        raise ValueError("Namecheap apply requires confirm=true")
    if not payload.get("backup_uri"):
        raise ValueError("Namecheap apply requires backup_uri")

    plan_payload = payload.get("plan") or {}
    desired = normalize_records(payload.get("desired_records") or plan_payload.get("desiredRecords"))
    if not desired:
        raise ValueError("Namecheap apply requires desired_records")

    current = current_records_fn(domain, payload)
    plan_current = plan_payload.get("currentRecords")
    if plan_current is not None and normalize_records(plan_current) != current and not payload.get("allow_current_drift"):
        raise ValueError("current DNS records differ from the reviewed plan")

    if payload.get("mock_apply"):
        return {
            "ok": True,
            "connector": CONNECTOR_ID,
            "type": "namecheap-dns",
            "action": "apply",
            "domain": domain,
            "applied": False,
            "mock": True,
            "desiredRecords": desired,
            "currentRecords": current,
        }

    config = config_from_env(payload.get("profile"))
    method = "POST" if len(desired) > 10 else "GET"
    response = request_api(config, "namecheap.domains.dns.setHosts", domain, sethosts_params(desired), method=method)
    parsed = parse_api_xml(response)
    if not parsed["ok"] or parsed.get("setSuccess") is False:
        raise ValueError(f"Namecheap setHosts failed: {parsed['errors']}")
    return {
        "ok": True,
        "connector": CONNECTOR_ID,
        "type": "namecheap-dns",
        "action": "apply",
        "domain": domain,
        "applied": True,
        "method": method,
        "response": parsed,
    }


def expected(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> dict[str, Any]:
    return {
        "ok": True,
        "connector": CONNECTOR_ID,
        "type": "namecheap-dns",
        "action": "expected",
        "expectedRecords": expected_records_fn(expected_records, expected_a, expected_aaaa),
    }


def expected_records_fn(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> dict[str, list[str]]:
    return expected_records(expected_records=expected_records, expected_a=expected_a, expected_aaaa=expected_aaaa)


def run_action(action: str, **kwargs: Any) -> dict[str, Any]:
    table = {
        "current": lambda **data: {
            "ok": True,
            "connector": CONNECTOR_ID,
            "type": "namecheap-dns",
            "action": "current",
            "domain": data.get("domain") or "localhost",
            "records": current_records(**data),
        },
        "expected": expected,
        "plan": plan,
        "backup": backup,
        "apply": apply,
    }
    if action not in table:
        raise ValueError(f"unsupported action: {action}")
    return table[action](**kwargs)


@DNS.command("records/query/current", meta={"label": "Current Namecheap DNS records"})
def current_command(domain: str = "", current_records: str = "", mock_records: str = "", profile: str = "") -> list[str]:
    return ["urirun-namecheap-dns", "current", "--domain", "{domain}", "--current-records", "{current_records}", "--mock-records", "{mock_records}", "--profile", "{profile}"]


@DNS.command("records/query/expected", meta={"label": "Expected DNS records"})
def expected_command(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> list[str]:
    return ["urirun-namecheap-dns", "expected", "--expected-records", "{expected_records}", "--expected-a", "{expected_a}", "--expected-aaaa", "{expected_aaaa}"]


@DNS.command("records/command/plan", meta={"label": "Plan Namecheap DNS changes"})
def plan_command(domain: str = "", current_records: str = "", desired_records: str = "", ensure_records: str = "", remove_records: str = "", mock_records: str = "", profile: str = "") -> list[str]:
    return ["urirun-namecheap-dns", "plan", "--domain", "{domain}", "--current-records", "{current_records}", "--desired-records", "{desired_records}", "--ensure-records", "{ensure_records}", "--remove-records", "{remove_records}", "--mock-records", "{mock_records}", "--profile", "{profile}"]


@DNS.command("records/command/backup", meta={"label": "Backup Namecheap DNS records"})
def backup_command(domain: str = "", current_records: str = "", mock_records: str = "", backup_dir: str = "", profile: str = "") -> list[str]:
    return ["urirun-namecheap-dns", "backup", "--domain", "{domain}", "--current-records", "{current_records}", "--mock-records", "{mock_records}", "--backup-dir", "{backup_dir}", "--profile", "{profile}"]


@DNS.command("records/command/apply", meta={"label": "Apply Namecheap DNS changes"})
def apply_command(domain: str = "", current_records: str = "", desired_records: str = "", plan: str = "", backup_uri: str = "", confirm: bool = False, mock_apply: bool = True, allow_current_drift: bool = False, profile: str = "") -> list[str]:
    return ["urirun-namecheap-dns", "apply", "--domain", "{domain}", "--current-records", "{current_records}", "--desired-records", "{desired_records}", "--plan", "{plan}", "--backup-uri", "{backup_uri}", "--confirm", "{confirm}", "--mock-apply", "{mock_apply}", "--allow-current-drift", "{allow_current_drift}", "--profile", "{profile}"]


def urirun_bindings() -> dict[str, Any]:
    return urirun.connector_bindings(connector=CONNECTOR_ID)

