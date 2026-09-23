from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    validators: list[str] = field(default_factory=list)
    benchmarks: list[str] = field(default_factory=list)
    supported_backends: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "validators": self.validators,
            "benchmarks": self.benchmarks,
            "supported_backends": self.supported_backends,
        }


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._register_defaults()

    def register(self, capability: Capability) -> None:
        self._capabilities[capability.id] = capability

    def get(self, capability_id: str) -> Capability | None:
        return self._capabilities.get(capability_id)

    def list_all(self) -> list[Capability]:
        return list(self._capabilities.values())

    def _register_defaults(self) -> None:
        self.register(
            Capability(
                id="structured_decision",
                name="Structured Decision",
                description="Fast discrete action selection or decision question answering over structured state.",
                validators=["schema_validity", "confidence_threshold"],
                benchmarks=["accuracy", "f1", "p95_latency"],
                supported_backends=["deterministic", "laya", "jev"],
            )
        )
        self.register(
            Capability(
                id="structured_extraction",
                name="Structured Extraction",
                description="Schema-constrained JSON data extraction from input text/transcripts.",
                validators=["json_schema_validity"],
                benchmarks=["accuracy", "field_f1", "schema_compliance"],
                supported_backends=["prompt", "lora", "qlora"],
            )
        )
        self.register(
            Capability(
                id="structured_generation",
                name="Structured Generation",
                description="Custom domain language generation with optional JSON structure.",
                validators=["json_schema_validity", "safety_refusal"],
                benchmarks=["rough_l", "bleu", "p95_latency"],
                supported_backends=["prompt", "rag", "lora", "qlora"],
            )
        )
        self.register(
            Capability(
                id="retrieval_grounding",
                name="Retrieval Grounding",
                description="Fact retrieval and knowledge grounding from domain packs.",
                validators=["fact_hallucination_check"],
                benchmarks=["hit_rate", "mrr", "relevance"],
                supported_backends=["edge_search", "rag"],
            )
        )


_DEFAULT_REGISTRY = CapabilityRegistry()


def get_capability_registry() -> CapabilityRegistry:
    return _DEFAULT_REGISTRY
