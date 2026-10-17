.PHONY: lint test db-test run-dev run-prod clear-db-dev

lint:
	ruff check .

TEST_DATABASE_URL ?= postgresql://test:test@localhost:5434/petcare_test

test:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) pytest -v --cov --cov-report=term-missing --cov-report=html

db-test:
	docker run -d --rm --name petcare-test-db -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=petcare_test -p 5434:5432 postgres:17

run-dev:
	docker compose up --build
run-prod:
	docker compose -f deploy/docker-compose.yml pull
	docker compose -f deploy/docker-compose.yml up
clear-db-dev:
	docker compose down -v
