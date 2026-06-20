.PHONY: help manifest bindings smoke test docker-test clean

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n",$$1,$$2}'

manifest: ## Print connector manifest
	python3 -m urirun_connector_namecheap_dns.cli manifest

bindings: ## Print urirun bindings
	python3 -m urirun_connector_namecheap_dns.cli bindings

smoke: ## Run CLI, registry, MCP and A2A smoke locally
	tmp=$$(mktemp -d); \
	mkdir -p "$$tmp/bin"; \
	printf '%s\n' '#!/usr/bin/env sh' 'exec python3 -m urirun_connector_namecheap_dns.cli "$$@"' > "$$tmp/bin/urirun-namecheap-dns"; \
	chmod +x "$$tmp/bin/urirun-namecheap-dns"; \
	export PATH="$$tmp/bin:$$PATH"; \
	python3 -m urirun_connector_namecheap_dns.cli plan \
	  --domain example.com \
	  --current-records '[{"Name":"@","Type":"A","Address":"203.0.113.10"}]' \
	  --desired-records '[{"Name":"@","Type":"A","Address":"203.0.113.11"}]' > "$$tmp/plan.json"; \
	python3 -m urirun_connector_namecheap_dns.cli bindings > "$$tmp/bindings.json"; \
	urirun validate "$$tmp/bindings.json"; \
	urirun compile "$$tmp/bindings.json" --out "$$tmp/registry.json"; \
	urirun run 'dns://host/records/command/plan' "$$tmp/registry.json" \
	  --payload '{"domain":"example.com","current_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]","desired_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.11\"}]"}' \
	  --execute --allow 'dns://host/*' > "$$tmp/run.json"; \
	python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data["ok"], data; out=json.loads(data["result"]["stdout"]); assert out["diff"]["changed"], out' "$$tmp/run.json"; \
	python3 -m urirun.v2_mcp tools "$$tmp/registry.json" > "$$tmp/tools.json"; \
	python3 -m urirun.v2_mcp card "$$tmp/registry.json" --name namecheap-dns --url http://localhost/ > "$$tmp/card.json"

test: ## Run connector tests
	python3 -m pytest -q

docker-test: ## Run connector in Docker and verify registry, MCP and A2A
	docker compose up --build --abort-on-container-exit --exit-code-from tester
	docker compose down -v --remove-orphans

clean: ## Remove local build/test artifacts
	rm -rf .pytest_cache .docker-smoke build dist *.egg-info

