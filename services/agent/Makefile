# AgentShield Agent Service Makefile

.PHONY: help install test run clean eval

help:
	@echo "AgentShield Agent Service"
	@echo ""
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make run        - Run service"
	@echo "  make test       - Run tests"
	@echo "  make eval       - Run model evaluation"
	@echo "  make clean      - Clean cache files"

install:
	pip install -e ".[dev]"

run:
	uvicorn app.main:app --reload --port 8003

test:
	pytest tests/ -v --cov=app

eval:
	python eval/model_eval.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
