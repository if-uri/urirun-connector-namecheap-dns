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
export NAMECHEAP_API_KEY=...          # literal key, OR a secrets-layer reference (below)
export NAMECHEAP_USERNAME=...
export NAMECHEAP_CLIENT_IP=...
export NAMECHEAP_SANDBOX=true
```

`NAMECHEAP_API_KEY` is **addressed by reference**: instead of the literal key it may
hold a urirun secrets-layer reference, resolved deny-by-default at use and never
copied around:

```bash
export NAMECHEAP_API_KEY='secret://keyring/namecheap#key'   # value lives in the OS keyring
# or: getv://NAMECHEAP_API_KEY_VALUE
# the allow-list defaults to the reference itself; widen with NAMECHEAP_SECRET_ALLOW
```

Profile-scoped vars (`NAMECHEAP_<PROFILE>_API_KEY`, …) work the same way.

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

## License

Released under the terms in [LICENSE](LICENSE).
