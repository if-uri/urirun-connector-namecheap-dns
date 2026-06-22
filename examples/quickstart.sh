#!/usr/bin/env bash
# namecheap-dns: install once, then run — auto-discovered, no registry path.
set -euo pipefail
urirun install urirun-connector-namecheap-dns            # local dev: pip install -e .
urirun run 'dns://host/records/query/expected' --payload '{}' --allow 'dns://*'
