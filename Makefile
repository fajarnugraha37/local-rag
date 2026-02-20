.PHONY: test eval all

test:
	python -m pytest -q

eval:
	python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results.json

all: test eval
