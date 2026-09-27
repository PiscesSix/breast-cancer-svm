PY ?= python
URL ?= http://127.0.0.1:8000

.PHONY: install train compare evaluate sample seed test lint run smoke tex slides all

install:
	$(PY) -m pip install -r requirements-dev.txt

train:
	$(PY) scripts/train.py

compare:
	$(PY) scripts/train_comparison.py

evaluate:
	$(PY) scripts/evaluate.py

sample:
	$(PY) scripts/make_sample_request.py

seed:
	$(PY) seed.py

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

# One process, like Render: dashboard at http://127.0.0.1:8000/
run:
	SERVICE_MODE=single $(PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

smoke:
	$(PY) scripts/smoke_test.py $(URL)

# Regenerate the LaTeX numbers and the Overleaf packages of the report and the slides.
tex:
	$(PY) docs/latex/make_tex_data.py
	$(PY) docs/latex/build_overleaf.py

slides: tex

all: train compare evaluate sample test lint tex
