.PHONY: demo run test selfcheck localstack-up localstack-boot localstack-cycle sam-build sam-deploy clean

# --- Build It (local, no AWS account) -----------------------------------
demo:
	python run.py --demo

run:
	python run.py

test:
	python -m unittest discover -s tests -t . -v

selfcheck:
	python scripts/selfcheck.py

# --- Local AWS (LocalStack) ---------------------------------------------
localstack-up:
	docker compose -f infra/localstack/docker-compose.yml up -d

localstack-boot:
	python scripts/localstack_bootstrap.py

localstack-cycle:
	python scripts/localstack_cycle.py

# --- Ship It (AWS / SAM) -------------------------------------------------
sam-build:
	sam build -t infra/template.yaml

sam-deploy:
	sam deploy -t infra/template.yaml --guided

clean:
	rm -rf .aws-sam data/alerts_outbox.json
