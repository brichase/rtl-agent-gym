PYTHON ?= /data/projects/rtl-agent-gym/venv/bin/python

.PHONY: smoke-test test clean

smoke-test:
	$(PYTHON) -m env.grade --smoke

test:
	$(PYTHON) -m unittest discover -s env/tests -v

clean:
	find env -type d -name __pycache__ -prune -exec rm -rf {} +
	find env -type f -name '*.pyc' -delete
