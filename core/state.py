from typing import TypedDict, List, Dict, Optional, Literal, Any

class TargetInfo(TypedDict):
    binary_path: str
    binary_type: Literal["ELF", "PE", "Mach-O", "Unknown"]
    arch: Optional[str]              # x86_64, arm64, etc.
    os: Optional[str]                # linux, windows, macos
    stripped: Optional[bool]
    protections: List[str]           # NX, PIE, CANARY, RELRO
    entrypoint: Optional[int]

class Goal(TypedDict):
    primary_objective: str
    sub_goals: List[str]

class Hypothesis(TypedDict):
    id: str
    claim: str
    confidence: float                # 0.0 – 1.0
    evidence: List[str]
    status: Literal["active", "confirmed", "rejected"]


class StringObservation(TypedDict):
    value: str
    offset: int
    encoding: Optional[str]


class CodeObservation(TypedDict):
    function_addr: int
    summary: str
    calls: List[int]
    xrefs: List[int]


class RuntimeObservation(TypedDict):
    breakpoint: str
    registers: Dict[str, int]
    memory: Optional[str]


class Observations(TypedDict):
    strings: List[StringObservation]
    code: List[CodeObservation]
    runtime: List[RuntimeObservation]

class Artifacts(TypedDict):
    decoded_strings: List[str]
    extracted_keys: List[str]
    decrypted_payloads: List[str]
    notes: List[str]

class PlanStep(TypedDict):
    step_id: int
    action: str
    tool: str
    status: Literal["pending", "completed", "failed"]
    result_ref: Optional[str]


class ExecutionLogEntry(TypedDict):
    step_id: int
    tool: str
    input: Dict[str, Any]
    output: Optional[str]
    error: Optional[str]

class Blocker(TypedDict):
    type: str                        # anti-debug, packing, crash
    description: str

class Confidence(TypedDict):
    understanding_level: float       # 0.0 – 1.0
    unanswered_questions: List[str]


class Termination(TypedDict):
    satisfied: bool
    reason: Optional[str]


class AgentState(TypedDict):
    target: TargetInfo
    goal: Goal

    hypotheses: List[Hypothesis]

    observations: Observations
    artifacts: Artifacts

    current_plan: List[PlanStep]
    execution_log: List[ExecutionLogEntry]

    blockers: List[Blocker]

    confidence: Confidence
    termination: Termination
