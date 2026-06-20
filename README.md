# urirun-connector-namecheap-dns

`namecheap-dns` exposes safe Namecheap DNS operations as URI commands for
`urirun` and ifURI.

The connector is intentionally conservative: `setHosts` replaces the full
Namecheap host record set, so apply requires a reviewed plan, a backup URI and
explicit confirmation. Tests and smoke checks use mock records and never call
the real Namecheap API.

## Routes

- `dns://host/records/query/current`
- `dns://host/records/query/expected`
- `dns://host/records/command/plan`
- `dns://host/records/command/backup`
- `dns://host/records/command/apply`

## Install

```bash
pip install "git+https://github.com/if-uri/urirun-connector-namecheap-dns.git@v0.1.0"
```

## Use

```bash
urirun-namecheap-dns bindings > bindings.json
urirun validate bindings.json
urirun compile bindings.json --out registry.json

urirun run 'dns://host/records/command/plan' registry.json \
  --payload '{"domain":"example.com","current_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]","desired_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.11\"}]"}' \
  --execute \
  --allow 'dns://host/*'
```

After installation, `urirun` can discover this connector automatically through
the `urirun.bindings` entry-point group:

```bash
urirun discover --out connectors.bindings.json --registry-out connectors.registry.json
urirun list --entry-points
```

For real API calls configure:

```bash
export NAMECHEAP_API_USER=...
export NAMECHEAP_API_KEY=...
export NAMECHEAP_USERNAME=...
export NAMECHEAP_CLIENT_IP=...
export NAMECHEAP_SANDBOX=true
```

## Test

```bash
make test
make smoke
make docker-test
```

## Related projects

- Runtime: [if-uri/urirun](https://github.com/if-uri/urirun)
- Docs: [docs.ifuri.com/connectors.html](https://docs.ifuri.com/connectors.html)
- Hub page: [connect.ifuri.com/connectors/namecheap-dns](https://connect.ifuri.com/connectors/namecheap-dns)
- Connector hub: [connect.ifuri.com](https://connect.ifuri.com)
- Domain flow connector: [if-uri/urirun-connector-domain-monitor](https://github.com/if-uri/urirun-connector-domain-monitor)

Repository notes: [TODO.md](TODO.md) · [CHANGELOG.md](CHANGELOG.md)
