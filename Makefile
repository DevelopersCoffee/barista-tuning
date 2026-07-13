.PHONY: setup setup-dev lint test rust-fmt rust-clippy rust-test flutter-test flutter-native-ffi-test package-android-ffi train eval publish

PYTHON ?= python3
UNAME_S := $(shell uname -s)
EDGE_FFI_LIBRARY := $(CURDIR)/target/debug/libedge_ffi.so
ifeq ($(UNAME_S),Darwin)
EDGE_FFI_LIBRARY := $(CURDIR)/target/debug/libedge_ffi.dylib
endif
ifneq (,$(filter MINGW% MSYS% CYGWIN%,$(UNAME_S)))
EDGE_FFI_LIBRARY := $(CURDIR)/target/debug/edge_ffi.dll
endif

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

flutter-test:
	cd bindings/flutter && dart analyze && dart test

flutter-native-ffi-test:
	cargo build -p edge-ffi
	cd bindings/flutter && \
		EDGE_FFI_LIBRARY="$(EDGE_FFI_LIBRARY)" \
		EDGE_FFI_PACK="$(CURDIR)/tests/fixtures/airo_iptv/media.iptv.airo-sample-0.1.0.pack" \
		EDGE_INTELLIGENCE_PACK_CACHE="$$(mktemp -d)" \
		dart test test/native_ffi_pack_test.dart

package-android-ffi:
	slm package-edge-ffi-android --airo-app ../airo/app --build --abi arm64-v8a

train:
	slm train configs/sft.yaml

eval:
	slm evaluate configs/sft.yaml

publish:
	slm publish configs/sft.yaml
