.PHONY: up down logs ingest eval eval-dev eval-release eval-acceptance test build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api agent web

ingest:
	curl --noproxy '*' -fsS -X POST "http://127.0.0.1:8000/api/ingest?force=true"

eval:
	cd apps/api && uv run python ../../evals/run_retrieval_eval.py

eval-dev:
	cd apps/api && uv run python ../../evals/run_agent_eval.py --set development --provider ollama --model qwen3:8b

eval-release:
	cd apps/api && uv run python ../../evals/run_agent_eval.py --set release --provider ollama --model qwen3:8b --resume

eval-acceptance:
	cd apps/api && uv run python ../../evals/run_agent_eval.py --set acceptance --provider ollama --resume

test:
	cd apps/api && uv run pytest -q
	cd services/agent && npm test
	cd apps/web && npm run lint
	cd apps/web && npm run build

build:
	cd services/agent && npm run build
	cd apps/web && npm run build
	docker compose config --quiet
