.PHONY: help fmt lint run-server run-cli chat chat-baseline chat-email ingest ingest-folder list-docs delete-doc ingest-email migrate-vault backfill backfill-namespaces query debug-retrieval validate eval test run-all all

PYTHON ?= python
APP := $(PYTHON) cmd/app.py
TOP_K ?= 6
Q ?= what are key payment terms?
KEYWORD ?= invoice
MODEL ?=
CITATIONS ?= true
CITATIONS_MODE ?= inline+sources
MAX_SOURCES ?= $(TOP_K)
MAX_SNIPPET_CHARS ?= 240
INGEST_PATH ?=
FOLDER_PATH ?=
DOC_ID ?=
NAMESPACE ?=
ALL_NAMESPACES ?= false

help:
	@$(info Available targets:)
	@$(info   make run-server)
	@$(info   make run-cli)
	@$(info   make chat TOP_K=6 CITATIONS=true CITATIONS_MODE=inline+sources MAX_SOURCES=6 MAX_SNIPPET_CHARS=240)
	@$(info   make chat-baseline CITATIONS=true CITATIONS_MODE=inline)
	@$(info   make chat-email CITATIONS=false)
	@$(info   make ingest INGEST_PATH="path\\to\\file_or_dir" NAMESPACE="default")
	@$(info   make ingest-folder FOLDER_PATH="path\\to\\folder" NAMESPACE="default")
	@$(info   make list-docs NAMESPACE="default")
	@$(info   make delete-doc DOC_ID="doc-id" NAMESPACE="default")
	@$(info   make delete-doc DOC_ID="doc-id" ALL_NAMESPACES=true)
	@$(info   make ingest-email KEYWORD="invoice")
	@$(info   make migrate-vault)
	@$(info   make backfill)
	@$(info   make backfill-namespaces)
	@$(info   make query Q="what are key payment terms?" TOP_K=6)
	@$(info   make debug-retrieval)
	@$(info   make validate)
	@$(info   make fmt)
	@$(info   make lint)
	@$(info   make test)
	@$(info   make eval)
	@$(info   make all)
	@$(info   make run-all)
	@:

fmt:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .

run-server:
	$(APP) --server --host 127.0.0.1 --port 8000

run-cli:
	$(APP) --cli --help

chat:
ifeq ($(strip $(CITATIONS)),false)
	$(APP) --cli chat --top-k $(TOP_K) --no-citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
else
	$(APP) --cli chat --top-k $(TOP_K) --citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
endif

chat-baseline:
ifeq ($(strip $(CITATIONS)),false)
	$(APP) --cli chat-baseline --no-citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
else
	$(APP) --cli chat-baseline --citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
endif

chat-email:
ifeq ($(strip $(CITATIONS)),false)
	$(APP) --cli chat-email --no-citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
else
	$(APP) --cli chat-email --citations --citations-mode "$(CITATIONS_MODE)" --max-sources $(MAX_SOURCES) --max-snippet-chars $(MAX_SNIPPET_CHARS)
endif

ingest:
ifeq ($(strip $(INGEST_PATH)),)
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli ingest-files --namespace "$(NAMESPACE)"
else
	$(APP) --cli ingest-files
endif
else
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli ingest-files --path "$(INGEST_PATH)" --namespace "$(NAMESPACE)"
else
	$(APP) --cli ingest-files --path "$(INGEST_PATH)"
endif
endif

ingest-folder:
ifeq ($(strip $(FOLDER_PATH)),)
	$(error FOLDER_PATH is required. Example: make ingest-folder FOLDER_PATH="docs")
endif
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli ingest-folder --path "$(FOLDER_PATH)" --namespace "$(NAMESPACE)"
else
	$(APP) --cli ingest-folder --path "$(FOLDER_PATH)"
endif

list-docs:
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli list-docs --namespace "$(NAMESPACE)"
else
	$(APP) --cli list-docs
endif

delete-doc:
ifeq ($(strip $(DOC_ID)),)
	$(error DOC_ID is required. Example: make delete-doc DOC_ID="my-doc")
endif
ifeq ($(strip $(ALL_NAMESPACES)),true)
	$(APP) --cli delete-doc --doc-id "$(DOC_ID)" --all-namespaces
else
ifneq ($(strip $(NAMESPACE)),)
	$(APP) --cli delete-doc --doc-id "$(DOC_ID)" --namespace "$(NAMESPACE)"
else
	$(APP) --cli delete-doc --doc-id "$(DOC_ID)"
endif
endif

ingest-email:
	$(APP) --cli ingest-email --keyword "$(KEYWORD)"

migrate-vault:
	$(APP) --cli migrate-vault --vault vault.txt

backfill:
	$(APP) --cli backfill-vectors --batch-size 64

backfill-namespaces:
	$(APP) --cli backfill-namespaces

query:
	$(APP) --cli query --query "$(Q)" --top-k $(TOP_K)

debug-retrieval:
	$(APP) --cli debug-retrieval

validate:
	$(APP) --cli validate-phase4 --top-k $(TOP_K)

test:
	$(PYTHON) -m pytest -q

eval:
	$(APP) --cli eval --questions eval\questions.jsonl --top-k $(TOP_K) --output eval\results.json

all: test eval

run-all: all
