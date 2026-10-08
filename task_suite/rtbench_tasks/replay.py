"""Deterministic contract fixtures. These are NOT physics simulation results."""
import copy
import random
import time
from dataclasses import asdict

from .catalog import TASKS
from .contracts import Action, Evidence, Observation, Receipt, Scenario


class ReplayPolicy:
    model_id = "diagnostic-recorded-policy"

    def __init__(self, actions):
        self.actions = iter((*actions, Action("finish")))
        self.requests = []

    def decide(self, request):
        self.requests.append(copy.deepcopy(request))
        return {"action": asdict(next(self.actions)), "memory": request["memory"]}


class ReplayBackend:
    mode = "replay"

    def __init__(self, actions, evidence, visible):
        self.actions, self.final_evidence, self.visible = tuple(actions), evidence, visible
        self.capabilities = frozenset(a.skill for a in actions)
        self.index, self.sequence, self.proof = 0, 0, {}

    def reset(self, scenario):
        if scenario.id != self.final_evidence.episode_id:
            raise ValueError("fixture episode mismatch")
        self.scenario = scenario
        self.index, self.sequence, self.proof = 0, 0, {}

    def observe(self):
        self.sequence += 1
        view = copy.deepcopy(self.visible)
        if self.scenario.task_id == "cover-blocks":
            covered = set()
            for a in self.actions[:self.index]:
                if a.skill == "cover":
                    covered.add(a.target_id)
                elif a.skill == "uncover":
                    covered.discard(self.scenario.truth["cover_to_block"][a.object_id])
            for o in covered:
                view["objects"][o] = {"occluded": True}
        if self.scenario.task_id == "press-by-number" and self.index:
            view["objects"] = {o: {"occluded": True} for o in self.scenario.objects}
        return Observation(self.scenario.id, self.sequence, time.monotonic_ns(), view)

    def execute(self, action, command_id, observation):
        if self.index >= len(self.actions) or action != self.actions[self.index]:
            self.proof = {"command_id": command_id, "verified": False}
            return Receipt(command_id, "failed", False, observation.sequence, "fixture action mismatch")
        self.index += 1
        self.sequence += 1
        self.proof = {"command_id": command_id, "verified": True}
        return Receipt(command_id, "completed", True, self.sequence, "recorded effect verified")

    def checkpoint(self):
        return dict(self.proof)

    def evidence(self):
        if self.index == len(self.actions):
            return self.final_evidence
        return Evidence(self.scenario.id, {o: {} for o in self.scenario.objects}, {}, (), "incomplete-replay-fixture", "fixture-v1")


def fixture(task_id, seed=0, *, digits_count=4):
    """Known-answer fixtures exercise contracts, ordering, routing and scoring."""
    task = TASKS[task_id]
    n = digits_count if task_id == "arrange-largest-number" else task.count or 6
    objects = tuple(f"object-{i}" for i in range(n))
    targets = ["table", "parking"]
    truth, facts, flags, events, actions = {}, {o: {"settled": True} for o in objects}, {"gripper_open": True, "robot_home": True}, [], []
    visible = {"objects": {o: {} for o in objects}, "targets": {}}

    def act(skill, obj, target="", orientation=""):
        actions.append(Action(skill, obj, target, orientation))

    if task_id in {"stack-bowls", "stack-blocks"}:
        for i, o in enumerate(objects):
            facts[o].update(support="table" if i == 0 else objects[i-1], upright=True)
            if i:
                act("stack", o, objects[i-1], "upright" if task_id == "stack-bowls" else "")
    elif task_id == "pack-objects-into-box":
        targets.append("box")
        truth["box"], flags["box_aligned"] = "box", True
        for o in objects:
            facts[o].update(container="box", orientation_valid=True)
            act("place", o, "box", "left")
    elif task_id == "hang-mugs":
        targets.append("rack")
        truth["rack"] = "rack"
        for o in objects:
            facts[o].update(container="rack", hung=True)
            act("hang", o, "rack")
    elif task_id == "arrange-largest-number":
        values = random.Random(seed).sample(range(10), n)
        truth["digits"] = dict(zip(objects, values))
        for o, value in truth["digits"].items():
            visible["objects"][o] = {"digit": value}
        for i, o in enumerate(sorted(objects, key=lambda x: truth["digits"][x], reverse=True)):
            target = f"pad-{i}"
            targets.append(target)
            facts[o].update(pad_index=i, orientation_valid=True)
            act("place", o, target, "preserve")
    elif task_id == "cover-blocks":
        colors = ["red", "green", "blue"]
        random.Random(seed).shuffle(colors)
        truth.update(left_to_right=list(objects), colors=dict(zip(objects, colors)), cover_to_block={})
        for i, o in enumerate(objects):
            cover = f"cover-{i}"
            targets.append(cover)
            truth["cover_to_block"][cover] = o
            visible["objects"][o] = {"color": colors[i], "left_to_right_index": i}
            facts[o]["covered"] = False
            act("cover", cover, o)
            events.append({"kind": "cover", "object_id": o})
        for color in ("red", "green", "blue"):
            o = objects[colors.index(color)]
            act("uncover", f"cover-{objects.index(o)}", "parking")
            events.append({"kind": "uncover", "object_id": o})
        flags["cups_orientation_valid"] = True
    elif task_id == "press-by-number":
        targets.extend(("button-0", "button-1", "confirm"))
        counts = [random.Random(seed).randint(1, 3), random.Random(seed+1).randint(1, 3)]
        truth.update(buttons=["button-0", "button-1"], counts=counts, confirm="confirm", protocol="two-stage-v1")
        for i, o in enumerate(objects):
            visible["objects"][o] = {"number": counts[i], "button": f"button-{i}"}
            for button in [f"button-{i}"] * counts[i] + ["confirm"]:
                act("press", button)
                events.append({"kind": "press", "object_id": button})
    elif task_id in {"insert-tubes", "plug-in-charger"}:
        truth["destinations"] = {}
        for i, o in enumerate(objects):
            target = f"slot-{i}"
            targets.append(target)
            truth["destinations"][o] = target
            facts[o].update(container=target, depth_valid=True, upright=True)
            act("insert", o, target, "upright")
    elif task_id in {"classify-objects", "classify-objects-by-language"}:
        baskets = ["left-basket", "middle-basket", "right-basket"]
        targets.extend(baskets)
        cats = {o: f"category-{i%3}" for i, o in enumerate(objects)}
        assignment = {f"category-{i}": baskets[i] for i in range(3)}
        truth.update(categories=cats, baskets=baskets, assignments=assignment)
        for o in objects:
            visible["objects"][o] = {"category": cats[o]}
            dest = assignment[cats[o]]
            facts[o]["container"] = dest
            act("place", o, dest)
    elif task_id == "play-stacking-toy":
        truth.update(groups={}, pegs={})
        index = 0
        for g, count in enumerate((4, 3, 2, 1)):
            group, peg = f"shape-{g}", f"peg-{g}"
            truth["pegs"][group] = peg
            targets.append(peg)
            for _ in range(count):
                o = objects[index]
                index += 1
                truth["groups"][o] = group
                visible["objects"][o] = {"shape": group}
                facts[o].update(container=peg, at_base=True, aligned=True)
                act("insert", o, peg)
    elif task_id == "align-blocks":
        targets.extend(("set-square", "row"))
        flags.update(alignment_valid=True, no_lift_entire_episode=True, used_set_square=True)
        act("push", "set-square", "row")
    else:
        raise ValueError(task_id)
    visible["targets"] = {t: {} for t in targets}
    instruction = task.instruction
    if task_id == "classify-objects-by-language":
        instruction += " " + "; ".join(f"{c} goes in {b}" for c, b in truth["assignments"].items())
    if task_id == "press-by-number":
        instruction += " Press button-0's count, confirm, then button-1's count, confirm again."
    actions.append(Action("home"))
    scenario = Scenario(f"{task_id}-seed-{seed}", task_id, seed, f"layout-{seed%5}", objects, tuple(targets), instruction, truth)
    evidence = Evidence(scenario.id, facts, flags, tuple(events), "known-answer-replay-fixture", "fixture-v1")
    return scenario, ReplayBackend(actions, evidence, visible), ReplayPolicy(actions)
