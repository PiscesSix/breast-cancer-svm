PY ?= python
URL ?= http://127.0.0.1:8000

.PHONY: install train evaluate test lint run smoke sample tex slides all

install:
	$(PY) -m pip install -r requirements-dev.txt

train:
	$(PY) scripts/train.py

evaluate:
	$(PY) scripts/evaluate.py

sample:
	$(PY) scripts/make_sample_request.py

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

run:
	$(PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

smoke:
	$(PY) scripts/smoke_test.py $(URL)

# Regenerate the LaTeX numbers and the Overleaf packages of the report and the slides.
tex:
	$(PY) docs/latex/make_tex_data.py
	$(PY) docs/latex/build_overleaf.py

slides: tex

all: train evaluate sample test lint tex
