.PHONY: setup setup-dev lint test rust-fmt rust-clippy rust-test flutter-test flutter-native-ffi-test package-android-ffi train eval publish airo-slm-predict airo-slm-compare airo-hf-bundle airo-hf-publish airo-hf-test-llama

PYTHON ?= python3
HF_REPO ?= developerscoffee/airo-media-actions-smollm2-135m
HF_PUBLISH_DIR ?= $(CURDIR)/.cache/hf-publish/airo-media-actions-smollm2-135m
AIRO_ADAPTER_DIR ?= $(CURDIR)/models/airo-media-actions-smollm2-135m
AIRO_LORA_GGUF ?= $(CURDIR)/models/gguf/airo-media-actions-lora-f16.gguf
AIRO_MERGED_GGUF ?= $(CURDIR)/models/gguf/airo-media-actions-smollm2-135m-merged-f16.gguf
AIRO_EVAL_DATA ?= $(CURDIR)/data/processed/airo_media_actions_eval.jsonl
AIRO_SLM_PREDICTIONS ?= $(CURDIR)/reports/airo_media_actions_slm_predictions.jsonl
AIRO_SLM_REPORT ?= $(CURDIR)/reports/airo_media_actions_rule_vs_slm.json
LLAMA_COMPLETION ?= llama-completion
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

airo-slm-predict:
	slm predict-media-actions \
		$(AIRO_EVAL_DATA) \
		$(AIRO_ADAPTER_DIR) \
		--output $(AIRO_SLM_PREDICTIONS)

airo-slm-compare:
	slm compare-media-action-predictions \
		$(AIRO_EVAL_DATA) \
		$(AIRO_SLM_PREDICTIONS) \
		--output $(AIRO_SLM_REPORT)

airo-hf-bundle:
	rm -rf "$(HF_PUBLISH_DIR)"
	mkdir -p "$(HF_PUBLISH_DIR)/peft-adapter" "$(HF_PUBLISH_DIR)/gguf" "$(HF_PUBLISH_DIR)/reports"
	cp docs/hf/airo-media-actions-model-card.md "$(HF_PUBLISH_DIR)/README.md"
	cp \
		"$(AIRO_ADAPTER_DIR)/adapter_config.json" \
		"$(AIRO_ADAPTER_DIR)/adapter_model.safetensors" \
		"$(AIRO_ADAPTER_DIR)/chat_template.jinja" \
		"$(AIRO_ADAPTER_DIR)/merges.txt" \
		"$(AIRO_ADAPTER_DIR)/special_tokens_map.json" \
		"$(AIRO_ADAPTER_DIR)/tokenizer.json" \
		"$(AIRO_ADAPTER_DIR)/tokenizer_config.json" \
		"$(AIRO_ADAPTER_DIR)/vocab.json" \
		"$(HF_PUBLISH_DIR)/peft-adapter/"
	cp "$(AIRO_LORA_GGUF)" "$(AIRO_MERGED_GGUF)" "$(HF_PUBLISH_DIR)/gguf/"
	cp "$(AIRO_SLM_REPORT)" "$(AIRO_SLM_PREDICTIONS)" "$(HF_PUBLISH_DIR)/reports/"
	@find "$(HF_PUBLISH_DIR)" -maxdepth 2 -type f | sort

airo-hf-publish: airo-hf-bundle
	$(PYTHON) -c "from pathlib import Path; from huggingface_hub import HfApi; repo='$(HF_REPO)'; folder=Path('$(HF_PUBLISH_DIR)'); api=HfApi(); api.create_repo(repo_id=repo, repo_type='model', private=False, exist_ok=True); commit=api.upload_folder(repo_id=repo, repo_type='model', folder_path=str(folder), commit_message='Publish Airo media actions edge model'); print(f'https://huggingface.co/{repo}'); print(commit.oid)"

airo-hf-test-llama:
	$(LLAMA_COMPLETION) \
		-m "$(AIRO_MERGED_GGUF)" \
		-p "$$(printf '### Instruction\nTranslate the Airo TV user request into a media action JSON object. Output JSON only. Do not answer conversationally.\n\n### Input\nShow Hindi news\n\n### Response\n')" \
		-n 128 \
		--temp 0 \
		--no-display-prompt \
		-no-cnv
