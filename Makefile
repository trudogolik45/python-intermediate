.PHONY: up build down test

up:
	docker compose up -d

build:
	docker compose up -d --build

down:
	docker compose down

test:
	docker compose -f docker-compose.test.yml up -d --build --remove-orphans
	docker compose -f docker-compose.test.yml exec -T test_app pytest -v; \
	status=$$?; \
	docker compose -f docker-compose.test.yml down -v; \
	exit $$status
