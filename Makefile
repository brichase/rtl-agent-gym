ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYTHON ?= $(ROOT)venv/bin/python

.PHONY: check-tools smoke-test leakage-check test clean

check-tools:
	@test -n "$$RTL_GYM_TOOLS" || { echo "error: RTL_GYM_TOOLS is not set; export it as the OSS CAD Suite bin/ directory (see README Quickstart)" >&2; exit 2; }

smoke-test: check-tools
	$(PYTHON) -m env.grade --smoke

leakage-check: check-tools
	$(PYTHON) -m agent.leakage_check

test: check-tools
	$(PYTHON) -m unittest discover -s env/tests -v

clean:
	find env -type d -name __pycache__ -prune -exec rm -rf {} +
	find env -type f -name '*.pyc' -delete
