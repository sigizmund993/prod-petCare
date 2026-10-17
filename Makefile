.PHONY: lint run-dev run-prod clear-db-dev

lint:
	ruff check .

run-dev:
	docker compose up --build
run-prod:
	docker compose -f deploy/docker-compose.yml pull
	docker compose -f deploy/docker-compose.yml up
clear-db-dev:
	docker compose down -v
