up:
	docker compose up --build

migrate:
	docker compose run --rm api alembic upgrade head

seed-admin:
	docker compose run --rm api python scripts/seed_admin.py
