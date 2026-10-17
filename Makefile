.PHONY: lint run-dev run-prod clear-db-dev

lint:
	ruff check .

run-dev:
	docker compose up --build
run-prod:
	docker compose -f docker-compose.prod.yaml pull
	docker compose -f docker-compose.prod.yaml up
clear-db-dev:
	docker compose down -v
