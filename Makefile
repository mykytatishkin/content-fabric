flake8: ## Run flake8 checks
	flake8 --ignore=F401 --max-line-length=99 --tee --exclude=tests --output-file=report/flake8.out routing_api/

pylint: ## Run pylint checks
	pylint -f parseable routing_api/ --ignore=routing_api/tests --rcfile=.pylintrc | tee report/pylint.out

lint: ## Run code checks
	flake8 routing_api && black -l 99 --check routing_api && isort -c routing_api

fmt: ## Run code formatting
	black -l 99 routing_api && isort routing_api

report: ## Create report folder
	[ -d report ] || mkdir -p report

build: ## Build local services
	@docker-compose build

up: ## Start local services
	docker-compose up --force-recreate localstack redis postgres

down: ## Stop local services
	docker-compose down

install: ## Install virtual environment and requirements
	source venv/bin/activate;pip install --upgrade pip;pip install -r requirements-test.txt;deactivate

installw: ## Install virtual environment and requirements
	call .venv/Scripts/activate && \
	python -m pip install --upgrade pip && \
	pip install -r requirements.txt

uninstall: ## Uninstall virtual environment and requirements
	source venv/bin/activate;pip install --upgrade pip;pip uninstall -r requirements-test.txt;deactivate

test: ## Run all tests
	find . -name \*.pyc -delete
	pytest -s -v --maxfail=2 routing_api/tests

test-cov: ## Run all tests with coverage report
	find . -name \*.pyc -delete
	pytest -s -v routing_api/tests --cov=routing_api --cov-report term --cov-report html:htmlcov

help: ## Print command reference
	@grep -E '^[a-zA-Z-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
