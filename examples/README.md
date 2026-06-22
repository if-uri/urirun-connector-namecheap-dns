# namecheap-dns connector — examples

Namecheap DNS records (gated by API creds).

## Install
```bash
urirun install urirun-connector-namecheap-dns
```
`urirun install` resolves catalog ids via connect.ifuri.com; `--catalog <url>` points at a
local/on-prem registry; a full package name / git URL / path falls back to `pip install`.

## Run
```bash
# Namecheap DNS records (gated by API creds) (read)
urirun run 'dns://host/records/query/expected' --payload '{}' --allow 'dns://*'

# preview without running (dry-run): drop --execute
urirun run 'dns://host/records/query/expected' --payload '{}' --allow 'dns://*'
```
> Config-gated: without runtime config this prints the plan (dry-run).

## Inspect the runtime (no path — like error:// / log://)
```bash
urirun list | grep 'dns://'                                   # this connector's routes
urirun run 'registry://local/routes/query/list' --payload '{"scheme":"dns"}' --allow 'registry://*'
urirun run 'registry://local/bindings/query/show' --payload '{"uri":"dns://host/records/query/expected"}' --allow 'registry://*'   # full typed contract
urirun errors                                                      # recent runtime errors (error://)
```

## Generate a client / API surface from the binding
```bash
urirun discover | urirun gen openapi - --out openapi.json   # OpenAPI 3 (one path per route)
urirun discover | urirun gen proto   - --out service.proto  # protobuf + gRPC (typed rpc per route)
urirun discover | urirun gen client  - --out client.py      # typed Python client
```
