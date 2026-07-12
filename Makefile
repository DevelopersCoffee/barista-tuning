.PHONY: setup setup-dev lint test rust-fmt rust-clippy rust-test train eval publish

PYTHON ?= python3

setup:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[all]"

setup-dev:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .

test:
	pytest

rust-fmt:
	cargo fmt --all -- --check

rust-clippy:
	cargo clippy --workspace --all-targets -- -D warnings

rust-test:
	cargo test --workspace

train:
	slm train configs/sft.yaml

eval:
	slm evaluate configs/sft.yaml

publish:
	slm publish configs/sft.yaml
