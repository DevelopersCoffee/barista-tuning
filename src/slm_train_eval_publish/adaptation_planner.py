from __future__ import annotations

import platform
from dataclasses import asdict, dataclass, field
from typing import Any

from slm_train_eval_publish.baseline import BaselineResult
from slm_train_eval_publish.capability import get_capability_registry
from slm_train_eval_publish.dataset_engine import DatasetProfile


@dataclass(frozen=True)
class HardwareProfile:
    device: str = "cpu"  # "cpu", "cuda", "apple_silicon_mlx"
    available_vram_gb: float = 0.0
    total_ram_gb: float = 16.0

    @classmethod
    def auto_detect(cls) -> HardwareProfile:
        system = platform.system()
        machine = platform.machine()
        if system == "Darwin" and machine == "arm64":
            return cls(device="apple_silicon_mlx", available_vram_gb=16.0, total_ram_gb=16.0)

        # Check CUDA availability if torch is present
        try:
            import torch
            if torch.cuda.is_available():
                vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                return cls(device="cuda", available_vram_gb=round(vram, 2))
        except ImportError:
            pass

        return cls(device="cpu", available_vram_gb=0.0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Constraints:
    target_f1: float = 0.85
    max_latency_p95_ms: float = 100.0
    max_memory_mb: float = 2048.0
    target_device: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlannerContext:
    task_id: str
    task_kind: str  # "decision", "classification", "extraction", "generation", "retrieval"
    capability_id: str  # "structured_decision", "structured_extraction", "structured_generation", "retrieval_grounding"
    dataset_profile: DatasetProfile
    baselines: list[BaselineResult] = field(default_factory=list)
    hardware: HardwareProfile = field(default_factory=HardwareProfile.auto_detect)
    constraints: Constraints = field(default_factory=Constraints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_kind": self.task_kind,
            "capability_id": self.capability_id,
            "dataset_profile": self.dataset_profile.to_dict(),
            "baselines": [b.to_dict() for b in self.baselines],
            "hardware": self.hardware.to_dict(),
            "constraints": self.constraints.to_dict(),
        }


@dataclass(frozen=True)
class AdaptationPlan:
    method: str  # "prompt", "rag", "decision", "lora", "qlora", "hybrid"
    backend: str  # "deterministic", "laya", "jev", "mlx", "transformers", "edge_search"
    configuration: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdaptationPlanner:
    @staticmethod
    def resolve(context: PlannerContext) -> AdaptationPlan:
        reasons: list[str] = []
        cap = get_capability_registry().get(context.capability_id)
        if cap:
            reasons.append(f"Evaluated capability '{cap.name}' ({cap.id}).")

        # 1. Check if any baseline already meets all constraints
        satisfying_baseline: BaselineResult | None = None
        for b in context.baselines:
            f1 = b.metrics.get("f1", b.metrics.get("accuracy", 0.0))
            if (
                f1 >= context.constraints.target_f1
                and b.latency_p95_ms <= context.constraints.max_latency_p95_ms
                and b.memory_mb <= context.constraints.max_memory_mb
            ):
                satisfying_baseline = b
                break

        if satisfying_baseline:
            reasons.append(
                f"Baseline backend '{satisfying_baseline.backend}' already satisfies target F1 "
                f"({satisfying_baseline.metrics.get('f1', 0.0)} >= {context.constraints.target_f1}) "
                f"and latency P95 ({satisfying_baseline.latency_p95_ms}ms <= {context.constraints.max_latency_p95_ms}ms)."
            )
            reasons.append("Fine-tuning is NOT required. Recommend deploying baseline solution.")
            method = "decision" if satisfying_baseline.backend in ("decision", "rule") else "prompt"
            return AdaptationPlan(
                method=method,
                backend=satisfying_baseline.backend,
                configuration={"deploy_baseline": True},
                reasons=reasons,
            )

        # 2. Decision Task Routing
        if context.task_kind == "decision" or context.capability_id == "structured_decision":
            reasons.append("Task is structured decision/action selection.")
            reasons.append(
                f"Target latency P95 requirement ({context.constraints.max_latency_p95_ms}ms) favours fast non-autoregressive decision engine."
            )
            selected_backend = "laya"
            if context.dataset_profile.total_examples > 2000:
                selected_backend = "jev"
                reasons.append("Large decision example volume favours Jev non-autoregressive backend.")
            else:
                reasons.append("Standard decision example volume selects Laya backend.")

            return AdaptationPlan(
                method="decision",
                backend=selected_backend,
                configuration={"threshold": 0.85, "fast_path_fallback": "deterministic"},
                reasons=reasons,
            )

        # 3. Retrieval Grounding Routing
        if context.task_kind == "retrieval" or context.capability_id == "retrieval_grounding":
            reasons.append("Task requires domain knowledge retrieval and grounding.")
            return AdaptationPlan(
                method="rag",
                backend="edge_search",
                configuration={"top_k": 5, "vector_index": "hnsw"},
                reasons=reasons,
            )

        # 4. Generative / Extraction SLM Adaptation (LoRA / QLoRA)
        reasons.append(
            f"Baselines failed target F1 ({context.constraints.target_f1}). Fine-tuning SLM adaptation required."
        )

        hw = context.hardware
        if hw.device == "apple_silicon_mlx":
            reasons.append("Detected Apple Silicon environment. Recommending MLX LoRA fine-tuning.")
            return AdaptationPlan(
                method="lora",
                backend="mlx",
                configuration={
                    "lora_layers": 16,
                    "lora_parameters": {"keys": ["q_proj", "v_proj"], "rank": 16, "scale": 32.0, "dropout": 0.0},
                },
                reasons=reasons,
            )

        if hw.device == "cuda" and hw.available_vram_gb <= 8.0:
            reasons.append(
                f"CUDA VRAM ({hw.available_vram_gb} GB) is under 8 GB budget. Recommending QLoRA 4-bit quantization."
            )
            return AdaptationPlan(
                method="qlora",
                backend="transformers",
                configuration={"quantization": "4bit", "rank": 16, "lora_alpha": 32},
                reasons=reasons,
            )

        reasons.append(f"Hardware ({hw.device}) supports standard LoRA adaptation.")
        return AdaptationPlan(
            method="lora",
            backend="transformers",
            configuration={"rank": 16, "lora_alpha": 32},
            reasons=reasons,
        )
