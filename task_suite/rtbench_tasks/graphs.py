"""Build thirteen native GaP graphs, with reusable manipulation subgraphs."""
from pathlib import Path

from .catalog import TASKS, SKILLS


SCRIPT = '''from typing import TypedDict

class Result(TypedDict):
    command_id: str

def run(ctx, *, skill: str, object_id: str, target_id: str, orientation: str) -> Result:
    return ctx.tool("se3.dispatch", action={"skill": skill, "object_id": object_id,
                    "target_id": target_id, "orientation": orientation})
'''


def build_all(destination):
    from gap.builder import Workflow, Subgraph, Ref
    root = Path(destination)
    if root.exists():
        raise FileExistsError(f"graph output already exists: {root}; use a fresh output directory")
    build_registry(root / "registry")
    for task in TASKS.values():
        directory = root / task.id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "scripts").mkdir(exist_ok=True)
        (directory / "scripts" / "dispatch.py").write_text(SCRIPT, encoding="utf-8")
        (directory / "checkpoints").mkdir(exist_ok=True)
        wf = Workflow(name=task.id, description="SE3 local task suite; bounded native GaP policy; replay/simulation adapters only.")
        wf.add_node("observe", type="tool", tool="se3.observe")
        wf.add_node("decide", type="tool", tool="se3.decide", inputs={"request": Ref("observe.request")})
        wf.add_node("done", type="end", status="success")
        wf.add_node("abort", type="end", status="failure")
        wf.add_edge("START", "observe")
        wf.add_edge("observe", "decide")
        mapping = {"finish": "done", "abort": "abort"}
        for skill in (*task.skills, "home"):
            name = f"{skill}_sg"
            sg = Subgraph(name=name, skill=f"se3-{skill}")
            fields = ("skill", "object_id", "target_id", "orientation")
            for field in fields:
                sg.add_input(field, type_name="str")
            sg.add_node("execute", type="script", script="scripts/dispatch.py", inputs={field: Ref(f"in.{field}") for field in fields})
            sg.add_exit("verified")
            sg.set_on_error("failed")
            sg.set_outputs(command_id=Ref("execute.command_id"))
            sg.add_edge("START", "execute")
            sg.add_edge("execute", "verified")
            sg.add_edge("verified", "END")
            # The native engine loads this sidecar after the subgraph. Its
            # snapshot is independent adapter verification of the last command.
            checkpoint = f'''from gap.runtime.verify import Checkpoint
CHECKPOINTS = [Checkpoint(name="verified_effect", subgraph={name!r},
    predicate=lambda world: world["verified"] is True,
    rationale="Adapter independently verifies the commanded skill effect.", validate=True)]
'''
            (directory / "checkpoints" / f"{name}.py").write_text(checkpoint, encoding="utf-8")
            wf.add_subgraph(sg)
            wf.add_node(skill, type="subgraph", ref=name, inputs={field: Ref(f"decide.action.{field}") for field in fields})
            wf.add_conditional_edges(skill, {"verified": "observe", "failed": "abort"}, router_field="exit")
            mapping[skill] = skill
        wf.add_conditional_edges("decide", mapping, router_field="route")
        wf.save(directory / "workflow.json")
    return root


def build_registry(root):
    """Reusable GaP skills; se3.* tools are bound by the episode harness."""
    root = Path(root)
    names = sorted(set(skill for task in TASKS.values() for skill in task.skills) | {"home"})
    for skill in names:
        directory = root / "skills" / f"se3-{skill}"
        (directory / "scripts").mkdir(parents=True, exist_ok=True)
        (directory / "scripts" / "dispatch.py").write_text(SCRIPT, encoding="utf-8")
        metadata = f'''---
name: se3-{skill}
description: "Use when the SE3 task needs the {skill} operation through a calibrated backend."
license: MIT
gap:
  requires: {{}}
  allowed_tools: [se3.dispatch]
  exit_conditions: {{verified: "Measured effect verified", failed: "Command failed or unverified"}}
  required_inputs: {{skill: str, object_id: str, target_id: str, orientation: str}}
  produces_outputs: {{command_id: str}}
  canonical_scripts:
    dispatch: scripts/dispatch.py
---

## When to use
{SKILLS[skill]}

## When NOT to use
Do not use without a backend capability declaration and calibrated effect checks.
These scripts do not contain robot motion controllers.

## Recommended subgraph state flow
Dispatch one command, require a completed receipt, then independently verify its
effect using the native GaP checkpoint. On unknown or failed status, terminate;
never automatically repeat a potentially completed command.

## Integration
The episode harness binds se3.dispatch to its own backend and registers its typed
callable in the native ToolRegistry. This bundle requires that harness tool.
'''
        (directory / "SKILL.md").write_text(metadata, encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "se3-task-skills"\nversion = "0.1.0"\n[project.optional-dependencies]\n' + ''.join(f'se3-{name} = []\n' for name in names), encoding="utf-8")
