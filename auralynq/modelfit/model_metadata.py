"""Model metadata schema for Auralynq ModelFit Index.

Fields are intentionally conservative: unknown values stay explicitly unknown
rather than being guessed. Measured benchmark data always overrides estimates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ModelSource = Literal["ollama", "huggingface", "local", "manual"]
ModelFamily = Literal[
    "llama", "qwen", "mistral", "gemma", "phi", "deepseek", "falcon", "mamba", "unknown"
]
ModelTask = Literal[
    "chat", "coding", "rag", "summarization", "agents", "vision", "multilingual", "math"
]
QuantizationLevel = Literal[
    "fp32",
    "fp16",
    "bf16",
    "int8",
    "q8",
    "q6_k",
    "q5_k",
    "q5_1",
    "q4_k",
    "q4_0",
    "q3_k",
    "q2_k",
]


@dataclass
class ModelMetadata:
    model_id: str
    source: ModelSource
    display_name: str = ""
    family: ModelFamily = "unknown"
    parameter_count_b: float | None = None  # None = unknown
    context_length: int | None = None
    license: str = "unknown"
    gated: bool = False
    tasks: list[ModelTask] = field(default_factory=list)
    available_quantizations: list[QuantizationLevel] = field(default_factory=list)
    embedding: bool = False
    reranker: bool = False
    supports_adapters: bool = False
    vision: bool = False
    tool_calling: bool = False
    multilingual: bool = False
    ollama_tag: str | None = None  # e.g. "llama3.1:8b"
    hf_repo: str | None = None  # e.g. "meta-llama/Meta-Llama-3.1-8B-Instruct"
    local_path: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "source": self.source,
            "display_name": self.display_name or self.model_id,
            "family": self.family,
            "parameter_count_b": self.parameter_count_b,
            "context_length": self.context_length,
            "license": self.license,
            "gated": self.gated,
            "tasks": self.tasks,
            "available_quantizations": self.available_quantizations,
            "embedding": self.embedding,
            "reranker": self.reranker,
            "supports_adapters": self.supports_adapters,
            "vision": self.vision,
            "tool_calling": self.tool_calling,
            "multilingual": self.multilingual,
            "ollama_tag": self.ollama_tag,
            "hf_repo": self.hf_repo,
            "local_path": self.local_path,
            "notes": self.notes,
        }
