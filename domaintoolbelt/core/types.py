from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
import uuid


class FidelityMode(str, Enum):
    STRICT = "strict"
    GROUNDED = "grounded"
    GUIDED = "guided"


class RetryStrategy(str, Enum):
    REPLAN = "replan"
    RETOOL = "retool"
    DEGRADE = "degrade"
    ABORT = "abort"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class FidelityPolicy:
    mode: FidelityMode = FidelityMode.GROUNDED
    require_citations: bool = True
    strict_verbatim_only: bool = False
    allow_unverified_paraphrase: bool = False
    allowed_source_scopes: tuple[str, ...] = ("primary",)
    forbidden_patterns: tuple[str, ...] = ()
    final_checks: tuple[str, ...] = ("citations", "scope", "tradition")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    authoritative: bool = False
    source_scope: str = "primary"
    tags: tuple[str, ...] = ()


@dataclass
class ToolRegistryConfig:
    max_tools_per_step: int = 5
    tool_timeout_seconds: float = 30.0
    embedding_model: str = "lexical-overlap"


@dataclass
class LLMConfig:
    enabled: bool = True
    planner_model: str = ""
    synthesizer_model: str = ""
    reranker_model: str = ""
    temperature: float = 0.1
    max_tokens: int = 2048
    structured_output: bool = False
    structured_fallback: bool = True


@dataclass
class RAGConfig:
    enabled: bool = True
    corpus_path: Path | None = None
    top_k_retrieval: int = 5
    similarity_threshold: float = 0.2
    fidelity_mode: FidelityMode = FidelityMode.GROUNDED
    verbatim_sources: tuple[str, ...] = ()


@dataclass
class MemoryConfig:
    enabled: bool = True
    store_path: Path = Path(".domaintoolbelt/memory")
    max_memory_inject: int = 5
    decay_half_life_days: float = 30.0


@dataclass
class ValidationConfig:
    strict_mode: bool = True
    max_retries: int = 2
    retry_strategy: RetryStrategy = RetryStrategy.RETOOL


@dataclass
class GuardrailConfig:
    tradition_flags: Mapping[str, str] = field(default_factory=dict)
    disallowed_inference_patterns: tuple[str, ...] = ()
    require_corpus_citation: bool = True
    require_primary_source: bool = False
    partner_mode_enabled: bool = False
    partner_mode_triggers: tuple[str, ...] = ()


@dataclass
class StreamingConfig:
    enabled: bool = True
    checkpoint_interval_steps: int = 2
    emit_step_headers: bool = True
    ui_mode: str = "tui"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    content: Any
    citations: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalAnswer:
    answer: str
    citations: tuple[str, ...] = ()
    confidence: float | None = None
    issues: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class PlanStep:
    step_id: str
    description: str
    instruction: str
    depends_on: tuple[str, ...] = ()
    preferred_tools: tuple[str, ...] = ()
    tool_name: str | None = None
    tool_args: Mapping[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING


@dataclass
class StepOutcome:
    step_id: str
    description: str
    tool_name: str
    instruction: str
    output: Any
    citations: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowContext:
    request: str
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    master_plan: str = ""
    plan: list[PlanStep] = field(default_factory=list)
    retrieved_context: list[str] = field(default_factory=list)
    memory_context: list[str] = field(default_factory=list)
    guardrail_notes: list[str] = field(default_factory=list)
    completed_steps: list[StepOutcome] = field(default_factory=list)
    grounding_report: Any | None = None
    final_answer: str = ""
    final_payload: FinalAnswer | None = None


@dataclass
class DomainConfig:
    key: str
    display_name: str
    description: str
    system_prompt_dir: Path
    fidelity: FidelityPolicy
    tools: tuple[ToolSpec, ...] = ()
    version: str = "0.1.0"
    authors: tuple[str, ...] = ()
    llm: LLMConfig = field(default_factory=LLMConfig)
    tool_registry: ToolRegistryConfig = field(default_factory=ToolRegistryConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    max_parallel_steps: int = 4
    tradition_flags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.system_prompt_dir = Path(self.system_prompt_dir)
        if self.rag.fidelity_mode == FidelityMode.STRICT:
            if not self.guardrails.require_corpus_citation:
                raise ValueError(
                    "STRICT fidelity mode requires guardrails.require_corpus_citation=True."
                )
