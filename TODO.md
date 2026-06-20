# TODO

- [x] Extract Namecheap DNS plan/backup/apply into an external connector.
- [x] Add local tests and Docker smoke coverage for mock DNS flows.
- [ ] Add this connector to IFURI-016 full host-node Docker matrix in safe
      dry-run/mock mode.
- [ ] Add environment-gated sandbox API integration tests.
- [ ] Publish route schemas, required environment variables and safety policy
      notes on the connector detail page.
- [x] Update `urirun-connector-domain-monitor` so it no longer imports
      `urirun.namecheap_dns` from core.
- [ ] Remove `urirun.namecheap_dns` compatibility code from core after downstream
      flows migrate.
