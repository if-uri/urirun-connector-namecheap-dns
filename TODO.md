# TODO

- [x] Extract Namecheap DNS plan/backup/apply into an external connector.
- [x] Add local tests and Docker smoke coverage for mock DNS flows.
- [ ] Add environment-gated sandbox API integration tests.
- [x] Update `urirun-connector-domain-monitor` so it no longer imports
      `urirun.namecheap_dns` from core.
- [ ] Remove `urirun.namecheap_dns` compatibility code from core after downstream
      flows migrate.
