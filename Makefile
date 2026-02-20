.PHONY: help run-server run-cli chat chat-baseline chat-email ingest ingest-email migrate-vault backfill query validate eval test run-all all

PYTHON ?= python
APP := $(PYTHON) cmd\app.py
TOP_K ?= 6
Q ?= what are key payment terms?
KEYWORD ?= invoice

help:
	@$(info Available targets:)
	@$(info   make run-server)
	@$(info   make run-cli)
	@$(info   make chat)
	@$(info   make chat-baseline)
	@$(info   make chat-email)
	@$(info   make ingest)
	@$(info   make ingest-email KEYWORD="invoice")
	@$(info   make migrate-vault)
	@$(info   make backfill)
	@$(info   make query Q="what are key payment terms?" TOP_K=6)
	@$(info   make validate)
	@$(info   make test)
	@$(info   make eval)
	@$(info   make all)
	@:

run-server:
	$(APP) --server --host 127.0.0.1 --port 8000

run-cli:
	$(APP) --cli --help

chat:
	$(APP) --cli chat --top-k $(TOP_K)

chat-baseline:
	$(APP) --cli chat-baseline

chat-email:
	$(APP) --cli chat-email

ingest:
	$(APP) --cli ingest-files

ingest-email:
	$(APP) --cli ingest-email --keyword "$(KEYWORD)"

migrate-vault:
	$(APP) --cli migrate-vault --vault vault.txt

backfill:
	$(APP) --cli backfill-vectors --batch-size 64

query:
	$(APP) --cli query --query "$(Q)" --top-k $(TOP_K)

validate:
	$(APP) --cli validate-phase4 --top-k $(TOP_K)

test:
	$(PYTHON) -m pytest -q

eval:
	$(APP) --cli eval --questions eval\questions.jsonl --top-k $(TOP_K) --output eval\results.json

all: test eval

run-all: all
