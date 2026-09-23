from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TokenStats:
    min: int = 0
    max: int = 0
    mean: float = 0.0
    p95: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetProfile:
    total_examples: int
    valid_examples: int
    invalid_examples: int
    duplicate_count: int
    exact_leakage_count: int
    normalized_leakage_count: int
    input_tokens: TokenStats
    output_tokens: TokenStats
    class_distribution: dict[str, int]
    schema_validity: float
    quality_warnings: list[str] = field(default_factory=list)
    dataset_hash: str = ""
    schema_hash: str = ""
    source_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["input_tokens"] = self.input_tokens.to_dict()
        d["output_tokens"] = self.output_tokens.to_dict()
        return d


@dataclass(frozen=True)
class DatasetPreparationConfig:
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1
    seed: int = 42
    deduplicate: bool = True
    leakage_policy: str = "fail"  # "fail", "remove_from_train", "remove_from_eval", "report_only"

    def canonical_json(self) -> str:
        return json.dumps(
            {
                "train_ratio": self.train_ratio,
                "val_ratio": self.val_ratio,
                "test_ratio": self.test_ratio,
                "seed": self.seed,
                "deduplicate": self.deduplicate,
                "leakage_policy": self.leakage_policy,
            },
            sort_keys=True,
        )


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_dataset_id(
    source_content: str,
    schema_content: str,
    prep_config: DatasetPreparationConfig,
) -> str:
    canonical = (
        source_content
        + "::"
        + schema_content
        + "::"
        + prep_config.canonical_json()
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def _calc_token_stats(tokens_list: list[int]) -> TokenStats:
    if not tokens_list:
        return TokenStats()
    sorted_t = sorted(tokens_list)
    n = len(sorted_t)
    min_val = sorted_t[0]
    max_val = sorted_t[-1]
    mean_val = round(sum(sorted_t) / float(n), 2)
    p95_idx = int(0.95 * (n - 1))
    p95_val = sorted_t[p95_idx]
    return TokenStats(min=min_val, max=max_val, mean=mean_val, p95=p95_val)


def inspect_dataset(
    source_path: Path,
    eval_path: Path | None = None,
    schema_path: Path | None = None,
) -> DatasetProfile:
    """Completely read-only inspection of a dataset (and optional eval split / schema)."""
    if not source_path.exists():
        raise FileNotFoundError(f"Dataset source file not found: {source_path}")

    source_content = source_path.read_text(encoding="utf-8")
    source_hash = _compute_hash(source_content)

    schema_content = ""
    schema_hash = ""
    schema_obj: dict[str, Any] | None = None
    if schema_path and schema_path.exists():
        schema_content = schema_path.read_text(encoding="utf-8")
        schema_hash = _compute_hash(schema_content)
        try:
            schema_obj = json.loads(schema_content)
        except Exception:
            schema_obj = None

    lines = [line.strip() for line in source_content.splitlines() if line.strip()]
    total_examples = len(lines)

    valid_count = 0
    invalid_count = 0
    exact_hashes: set[str] = set()
    normalized_hashes: set[str] = set()
    duplicate_count = 0

    input_tokens_list: list[int] = []
    output_tokens_list: list[int] = []
    class_dist: dict[str, int] = {}
    quality_warnings: list[str] = []

    for line in lines:
        try:
            ex = json.loads(line)
        except json.JSONDecodeError:
            invalid_count += 1
            continue

        valid_count += 1

        # Check duplicate
        raw_repr = json.dumps(ex, sort_keys=True)
        raw_h = _compute_hash(raw_repr)
        norm_repr = _normalize_text(raw_repr)
        norm_h = _compute_hash(norm_repr)

        if raw_h in exact_hashes or norm_h in normalized_hashes:
            duplicate_count += 1
        else:
            exact_hashes.add(raw_h)
            normalized_hashes.add(norm_h)

        # Token length stats
        input_text = ""
        output_text = ""
        if isinstance(ex, dict):
            if "input" in ex:
                input_text = str(ex["input"])
            elif "prompt" in ex:
                input_text = str(ex["prompt"])
            elif "messages" in ex and isinstance(ex["messages"], list):
                input_text = " ".join(
                    str(m.get("content", ""))
                    for m in ex["messages"]
                    if isinstance(m, dict) and m.get("role") != "assistant"
                )

            if "output" in ex:
                output_text = str(ex["output"])
            elif "completion" in ex:
                output_text = str(ex["completion"])
            elif "messages" in ex and isinstance(ex["messages"], list):
                output_text = " ".join(
                    str(m.get("content", ""))
                    for m in ex["messages"]
                    if isinstance(m, dict) and m.get("role") == "assistant"
                )

            # Class distribution / label tracking
            label = ex.get("label") or ex.get("action") or ex.get("intent") or ex.get("category")
            if label:
                l_str = str(label)
                class_dist[l_str] = class_dist.get(l_str, 0) + 1

        input_tokens_list.append(_estimate_tokens(input_text))
        output_tokens_list.append(_estimate_tokens(output_text))

    # Leakage check with eval_path if present
    exact_leakage = 0
    normalized_leakage = 0
    if eval_path and eval_path.exists():
        eval_content = eval_path.read_text(encoding="utf-8")
        eval_lines = [l.strip() for l in eval_content.splitlines() if l.strip()]
        for line in eval_lines:
            try:
                ex = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw_h = _compute_hash(json.dumps(ex, sort_keys=True))
            norm_h = _compute_hash(_normalize_text(json.dumps(ex, sort_keys=True)))
            if raw_h in exact_hashes:
                exact_leakage += 1
            if norm_h in normalized_hashes:
                normalized_leakage += 1

    schema_validity = (valid_count / float(total_examples)) if total_examples > 0 else 0.0

    if duplicate_count > 0:
        quality_warnings.append(f"Detected {duplicate_count} duplicate or near-duplicate examples.")
    if exact_leakage > 0:
        quality_warnings.append(f"Detected {exact_leakage} exact train/eval leakage examples.")
    if normalized_leakage > exact_leakage:
        quality_warnings.append(
            f"Detected {normalized_leakage - exact_leakage} normalized near-leakage examples between train and eval."
        )
    if invalid_count > 0:
        quality_warnings.append(f"Found {invalid_count} malformed JSON lines in dataset.")

    # Class imbalance warning
    if class_dist:
        counts = list(class_dist.values())
        max_c = max(counts)
        min_c = min(counts)
        if min_c > 0 and (max_c / float(min_c)) > 5.0:
            quality_warnings.append(
                f"Class imbalance detected (ratio max/min is {round(max_c / float(min_c), 1)}:1)."
            )

    return DatasetProfile(
        total_examples=total_examples,
        valid_examples=valid_count,
        invalid_examples=invalid_count,
        duplicate_count=duplicate_count,
        exact_leakage_count=exact_leakage,
        normalized_leakage_count=normalized_leakage,
        input_tokens=_calc_token_stats(input_tokens_list),
        output_tokens=_calc_token_stats(output_tokens_list),
        class_distribution=class_dist,
        schema_validity=round(schema_validity, 4),
        quality_warnings=quality_warnings,
        dataset_hash="",  # computed upon snapshot preparation
        schema_hash=schema_hash,
        source_hash=source_hash,
    )


def prepare_dataset(
    source_path: Path,
    output_dir: Path,
    config: DatasetPreparationConfig = DatasetPreparationConfig(),
    eval_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Generates an immutable DatasetSnapshot under output_dir/.slm/datasets/<dataset_id>/."""
    profile = inspect_dataset(source_path=source_path, eval_path=eval_path, schema_path=schema_path)

    # Check leakage policy
    if profile.exact_leakage_count > 0 or profile.normalized_leakage_count > 0:
        if config.leakage_policy == "fail":
            raise ValueError(
                f"Dataset preparation aborted: {profile.exact_leakage_count} exact / "
                f"{profile.normalized_leakage_count} normalized leakage examples detected between train and eval splits."
            )

    source_content = source_path.read_text(encoding="utf-8")
    schema_content = schema_path.read_text(encoding="utf-8") if (schema_path and schema_path.exists()) else ""

    dataset_id = compute_dataset_id(source_content, schema_content, config)
    snapshot_dir = output_dir / ".slm" / "datasets" / dataset_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Load and clean lines
    lines = [line.strip() for line in source_content.splitlines() if line.strip()]
    seen_hashes: set[str] = set()
    cleaned_examples: list[dict[str, Any]] = []

    for line in lines:
        try:
            ex = json.loads(line)
        except json.JSONDecodeError:
            continue

        if config.deduplicate:
            h = _compute_hash(_normalize_text(json.dumps(ex, sort_keys=True)))
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

        cleaned_examples.append(ex)

    # Deterministic split
    import random
    rng = random.Random(config.seed)
    rng.shuffle(cleaned_examples)

    total = len(cleaned_examples)
    n_train = int(total * config.train_ratio)
    n_val = int(total * config.val_ratio)

    train_data = cleaned_examples[:n_train]
    val_data = cleaned_examples[n_train : n_train + n_val]
    test_data = cleaned_examples[n_train + n_val :]

    # Write split files
    train_file = snapshot_dir / "train.jsonl"
    val_file = snapshot_dir / "validation.jsonl"
    test_file = snapshot_dir / "test.jsonl"

    with train_file.open("w", encoding="utf-8") as f:
        for ex in train_data:
            f.write(json.dumps(ex) + "\n")

    with val_file.open("w", encoding="utf-8") as f:
        for ex in val_data:
            f.write(json.dumps(ex) + "\n")

    with test_file.open("w", encoding="utf-8") as f:
        for ex in test_data:
            f.write(json.dumps(ex) + "\n")

    # Update profile with snapshot dataset_id
    profile_dict = profile.to_dict()
    profile_dict["dataset_hash"] = dataset_id

    profile_file = snapshot_dir / "profile.json"
    profile_file.write_text(json.dumps(profile_dict, indent=2), encoding="utf-8")

    manifest = {
        "dataset_id": dataset_id,
        "source_path": str(source_path),
        "source_hash": profile.source_hash,
        "schema_path": str(schema_path) if schema_path else None,
        "schema_hash": profile.schema_hash,
        "prep_config": json.loads(config.canonical_json()),
        "splits": {
            "train": {"path": str(train_file), "count": len(train_data)},
            "validation": {"path": str(val_file), "count": len(val_data)},
            "test": {"path": str(test_file), "count": len(test_data)},
        },
    }
    manifest_file = snapshot_dir / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "dataset_id": dataset_id,
        "snapshot_dir": str(snapshot_dir),
        "manifest": manifest,
        "profile": profile_dict,
    }
