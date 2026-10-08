"""Public observations and private evaluation truth have separate types."""
from dataclasses import dataclass, field
from typing import Protocol

from .catalog import TASKS, catalog


@dataclass(frozen=True)
class Scenario:
    id: str
    task_id: str
    seed: int
    layout: str
    objects: tuple[str, ...]
    targets: tuple[str, ...]
    instruction: str
    truth: dict = field(repr=False)
    corrections: tuple[tuple[int, str], ...] = ()
    mask_instruction_after: int | None = None

    def __post_init__(self):
        task = TASKS[self.task_id]
        if not self.id or not self.layout or not self.instruction:
            raise ValueError("scenario id, layout and instruction are required")
        if len(set(self.objects)) != len(self.objects) or not self.objects:
            raise ValueError("object ids must be unique and nonempty")
        if len(set(self.targets)) != len(self.targets) or not self.targets:
            raise ValueError("target ids must be unique and nonempty")
        if task.count and len(self.objects) != task.count:
            if not (task.id == "arrange-largest-number" and len(self.objects) == 5):
                raise ValueError("wrong object count for task")
        if self.mask_instruction_after is not None and self.mask_instruction_after < 1:
            raise ValueError("mask only after at least one policy observation")
        if any(step < 0 or not text for step, text in self.corrections):
            raise ValueError("invalid correction schedule")


@dataclass(frozen=True)
class Observation:
    episode_id: str
    sequence: int
    captured_ns: int
    visible: dict
    # The backend must remove occluded attributes before constructing visible.
    # IDs must be neutral (block-0, not red-block) in memory tasks.


@dataclass(frozen=True)
class Action:
    skill: str
    object_id: str = ""
    target_id: str = ""
    orientation: str = ""

    def validate(self, scenario):
        if self.skill not in catalog(scenario.task_id):
            raise ValueError(f"unsupported task skill: {self.skill}")
        if self.skill in {"home", "finish", "abort"}:
            if self.object_id or self.target_id or self.orientation:
                raise ValueError("terminal/home command cannot carry manipulation arguments")
            return
        if self.object_id not in scenario.objects + scenario.targets:
            raise ValueError("unknown object/tool/button id")
        if self.skill != "press" and self.target_id not in scenario.targets + scenario.objects:
            raise ValueError("unknown target id")
        if self.skill == "press" and (self.target_id or self.orientation):
            raise ValueError("press is a single button event")
        if self.orientation not in {"", "left", "upright", "preserve"}:
            raise ValueError("unsupported orientation constraint")


@dataclass(frozen=True)
class Receipt:
    command_id: str
    status: str  # completed | failed | unknown
    verified: bool
    observation_sequence: int
    public_feedback: str = ""


@dataclass(frozen=True)
class Evidence:
    """Adapter/evaluator facts, NEVER model-supplied assertions.

    Booleans certify measurements against the episode's frozen calibration.
    Missing/false facts cannot earn credit. Events describe observed effects,
    not requested actions. Raw telemetry reference is retained for audit.
    """
    episode_id: str
    objects: dict[str, dict]
    flags: dict[str, bool]
    events: tuple[dict, ...]
    source: str
    calibration_id: str
    telemetry_ref: str = ""


class Backend(Protocol):
    mode: str
    capabilities: frozenset[str]
    def reset(self, scenario: Scenario) -> None: ...
    def observe(self) -> Observation: ...
    def execute(self, action: Action, command_id: str, observation: Observation) -> Receipt: ...
    def checkpoint(self) -> dict:
        """Independent last-command proof: command_id and verified boolean."""
        ...
    def evidence(self) -> Evidence: ...


class Policy(Protocol):
    model_id: str
    def decide(self, request: dict) -> dict:
        """Return exactly {'action': Action-as-dict, 'memory': str}."""
        ...
