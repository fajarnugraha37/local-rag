.PHONY: help install setup fmt lint run-server run-cli shell cli-smoke chat chat-baseline chat-email ingest ingest-folder list-docs delete-doc ingest-email migrate-vault backfill backfill-namespaces query debug-retrieval validate ingest-smoke eval test idempotency-purge purge-soft-deletes run-all all

PYTHON ?= python
APP := $(PYTHON) cmd/app.py
TOP_K ?= 6
Q ?= what are key payment terms?
KEYWORD ?= invoice
CITATIONS ?= true
CITATIONS_MODE ?= inline+sources
MAX_SOURCES ?= $(TOP_K)
MAX_SNIPPET_CHARS ?= 240
INGEST_PATH ?=
FOLDER_PATH ?=
DOC_ID ?=
NAMESPACE ?=
ALL_NAMESPACES ?= false
SOFT_DELETE_RETENTION_DAYS ?= 30

help:
	@$(info Available targets:)
	@$(info   make install)
	@$(info   make setup)
	@$(info   make fmt)
	@$(info   make lint)
	@$(info   make test)
	@$(info   make run-server)
	@$(info   make run-cli)
	@$(info   make shell)
	@$(info   make cli-smoke)
	@$(info   make query Q="what are key payment terms?" TOP_K=6)
	@$(info   make idempotency-purge)
	@$(info   make purge-soft-deletes SOFT_DELETE_RETENTION_DAYS=30)
	@$(info   make eval)
	@$(info   make all)
	@$(info   make run-all)
	@$(info Legacy action wrappers:)
	@$(info   make chat / chat-baseline / chat-email)
	@$(info   make ingest / ingest-folder / list-docs / delete-doc / ingest-email)
	@$(info   make migrate-vault / backfill / backfill-namespaces / debug-retrieval / validate)
	@:

install:
	$(PYTHON) -m pip install -r requirements.txt

setup:
	$(PYTHON) -m pip install -r requirements.txt

fmt:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .

run-server:
	$(APP) --server --host 127.0.0.1 --port 8000

run-cli:
	$(APP) --cli --help

shell:
	$(APP) --cli shell

cli-smoke:
	$(APP) --cli healthz --json
	$(APP) --cli version --json
	$(APP) --cli capabilities --json
	$(APP) --cli ns list --json
	$(APP) --cli doc list --limit 1 --json

# Legacy action wrappers (kept for backward compatibility)
chat:
ifeq ($(strip $(CITATIONS)),false)
	$(APP) --cli actions chat --top-k $(TOP_K) --no-citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
else
	$(APP) --cli actions chat --top-k $(TOP_K) --citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
endif

chat-baseline:
ifeq ($(strip $(CITATIONS)),false)
	$(APP) --cli actions chat-baseline --no-citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
else
	$(APP) --cli actions chat-baseline --citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
endif

chat-email:
ifeq ($(strip $(CITATIONS)),false)
	$(APP) --cli actions chat-email --no-citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
else
	$(APP) --cli actions chat-email --citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
endif

ingest:
ifeq ($(strip $(INGEST_PATH)),)
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli actions ingest-files --namespace "$(NAMESPACE)"
else
	$(APP) --cli actions ingest-files
endif
else
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli actions ingest-files --path "$(INGEST_PATH)" --namespace "$(NAMESPACE)"
else
	$(APP) --cli actions ingest-files --path "$(INGEST_PATH)"
endif
endif

ingest-folder:
ifeq ($(strip $(FOLDER_PATH)),)
	$(error FOLDER_PATH is required. Example: make ingest-folder FOLDER_PATH="docs")
endif
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli actions ingest-folder --path "$(FOLDER_PATH)" --namespace "$(NAMESPACE)"
else
	$(APP) --cli actions ingest-folder --path "$(FOLDER_PATH)"
endif

list-docs:
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli actions list-docs --namespace "$(NAMESPACE)"
else
	$(APP) --cli actions list-docs
endif

delete-doc:
ifeq ($(strip $(DOC_ID)),)
	$(error DOC_ID is required. Example: make delete-doc DOC_ID="my-doc")
endif
ifeq ($(strip $(ALL_NAMESPACES)),true)
	$(APP) --cli actions delete-doc --doc-id "$(DOC_ID)" --all-namespaces
else
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli actions delete-doc --doc-id "$(DOC_ID)" --namespace "$(NAMESPACE)"
else
	$(APP) --cli actions delete-doc --doc-id "$(DOC_ID)"
endif
endif

ingest-email:
	$(APP) --cli actions ingest-email --keyword "$(KEYWORD)"

migrate-vault:
	$(APP) --cli actions migrate-vault --vault vault.txt

backfill:
	$(APP) --cli actions backfill-vectors --batch-size 64

backfill-namespaces:
	$(APP) --cli actions backfill-namespaces

query:
	$(APP) --cli query "$(Q)" --top-k $(TOP_K)

debug-retrieval:
	$(APP) --cli actions debug-retrieval

validate:
	$(APP) --cli actions validate-phase4 --top-k $(TOP_K)

test:
	$(PYTHON) -m pytest -q

ingest-smoke:
	$(PYTHON) -m pytest -q tests/test_smoke_ingest.py tests/test_docling_ingestion_smoke.py

idempotency-purge:
	$(PYTHON) -c "from app.config.runtime_settings import CONFIG; from app.repositories.sqlite.idempotency_repo import IdempotencyRepository; repo=IdempotencyRepository(str(CONFIG.get('sqlite_db_path','data/app.db'))); print({'deleted': repo.delete_expired()})"

purge-soft-deletes:
	$(PYTHON) -c "from app.config.runtime_settings import CONFIG; from app.repositories.sqlite.documents_repo import DocumentsRepository; from app.repositories.sqlite.namespaces_repo import NamespacesRepository; db=str(CONFIG.get('sqlite_db_path','data/app.db')); days=int('$(SOFT_DELETE_RETENTION_DAYS)'); docs=DocumentsRepository(db).purge_soft_deleted(retention_days=days); nss=NamespacesRepository(db).purge_soft_deleted(retention_days=days); print({'documents_deleted': docs, 'namespaces_deleted': nss, 'retention_days': days})"

eval:
	$(APP) --cli actions eval --questions eval\questions.jsonl --top-k $(TOP_K) --output eval\results.json

all: test eval

run-all: all
