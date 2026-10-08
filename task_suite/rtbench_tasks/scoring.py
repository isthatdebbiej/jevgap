"""Deterministic local rubric. Geometry is certified by an external evaluator.

The policy has no access to this module's private scenario truth or evidence.
"""
from dataclasses import dataclass

from .catalog import TASKS
from .contracts import Evidence, Scenario


@dataclass(frozen=True)
class Score:
    points: int
    success: bool
    complete_units: int
    rubric: str = "se3-local-v1"


def evaluate(s: Scenario, e: Evidence) -> Score:
    if e.episode_id != s.id:
        raise ValueError("evidence belongs to another episode")
    if not e.source or not e.calibration_id:
        raise ValueError("evaluation source and frozen calibration are required")
    if not set(s.objects).issubset(e.objects):
        raise ValueError("incomplete object evidence")
    if any(type(v) is not bool for v in e.flags.values()):
        raise ValueError("flags must be measured booleans")
    task, truth = TASKS[s.task_id], s.truth
    home = e.flags.get("robot_home") is True
    released = e.flags.get("gripper_open") is True

    def valid(oid, *fields):
        return all(e.objects[oid].get(k) is True for k in fields)

    def levels(n, total, partial):
        if n == total and home:
            return Score(100, True, n)
        # Intermediate tiers with explicit release requirements are enforced
        # conservatively at all partial tiers in this local implementation.
        points = partial[min(n, len(partial) - 1)] if released else 0
        return Score(points, False, n)

    if task.id in {"stack-blocks", "stack-bowls"}:
        def chain(oid, seen):
            if oid in seen or not valid(oid, "settled"):
                return 0
            if task.id == "stack-bowls" and not valid(oid, "upright"):
                return 0
            support = e.objects[oid].get("support")
            if support == "table":
                return 1
            if support not in s.objects:
                return 0
            lower = chain(support, seen | {oid})
            return lower + 1 if lower else 0
        n = max(chain(o, set()) for o in s.objects)
        return levels(n, 3, (0, 0, 15))

    if task.id == "pack-objects-into-box":
        box = truth["box"]
        n = sum(e.objects[o].get("container") == box and valid(o, "orientation_valid", "settled")
                for o in s.objects) if e.flags.get("box_aligned") is True else 0
        return levels(n, 4, (0, 10, 25, 50))

    if task.id == "hang-mugs":
        n = sum(e.objects[o].get("container") == truth["rack"] and valid(o, "hung", "settled") for o in s.objects)
        return levels(n, 3, (0, 15, 40))

    if task.id == "arrange-largest-number":
        digits = truth["digits"]
        if set(digits) != set(s.objects) or any(type(v) is not int or not 0 <= v <= 9 for v in digits.values()):
            raise ValueError("requires one digit 0..9 per tile")
        desired = sorted(digits.values(), reverse=True)
        # Repeated digits are interchangeable; duplicate occupancy earns no credit.
        slots = [e.objects[o].get("pad_index") for o in s.objects]
        n = sum(type(i) is int and 0 <= i < len(desired) and slots.count(i) == 1
                and digits[o] == desired[i] and valid(o, "orientation_valid", "settled")
                for o, i in zip(s.objects, slots))
        partial = (0, 5, 15, 30) if len(s.objects) == 4 else (0, 5, 15, 25, 40)
        return levels(n, len(s.objects), partial)

    if task.id == "cover-blocks":
        order = truth["left_to_right"]
        colors = truth["colors"]
        if set(order) != set(s.objects) or len(order) != 3 or set(colors) != set(s.objects) or set(colors.values()) != {"red", "green", "blue"}:
            raise ValueError("invalid cover-blocks truth")
        wanted = [("cover", o) for o in order] + [("uncover", next(o for o in s.objects if colors[o] == c)) for c in ("red", "green", "blue")]
        events = [(a.get("kind"), a.get("object_id")) for a in e.events if a.get("kind") in {"cover", "uncover"}]
        if len(events) < 3 or len(events) > 6 or events != wanted[:len(events)]:
            return Score(0, False, 0)
        n = len(events) - 3
        uncovered = {o for _, o in wanted[3:3+n]}
        if any(e.objects[o].get("covered") is not (o not in uncovered) for o in s.objects):
            return Score(0, False, n)
        success = n == 3 and home and e.flags.get("cups_orientation_valid") is True
        return Score(100 if success else (5, 15, 30, 30)[n], success, n)

    if task.id == "press-by-number":
        if truth.get("protocol") != "two-stage-v1":
            raise ValueError("unresolved press protocol: explicitly select two-stage-v1 from the scoring table")
        buttons, counts = truth["buttons"], truth["counts"]
        if len(buttons) != 2 or len(set(buttons)) != 2 or len(counts) != 2 or any(type(n) is not int or n < 0 for n in counts):
            raise ValueError("invalid button counts")
        expected = [buttons[0]] * counts[0] + [truth["confirm"]] + [buttons[1]] * counts[1] + [truth["confirm"]]
        observed = [a.get("object_id") for a in e.events if a.get("kind") == "press"]
        success = observed == expected and home
        return Score(100 if success else 0, success, int(success))

    if task.id in {"plug-in-charger", "insert-tubes"}:
        targets = truth["destinations"]
        n = sum(e.objects[o].get("container") == targets[o] and valid(o, "depth_valid", "upright", "settled") for o in s.objects)
        # Every tube needs a distinct slot; one charger uses one socket.
        if len(set(targets.values())) != len(s.objects):
            raise ValueError("insertion targets must be distinct")
        return levels(n, len(s.objects), (0,) if task.id == "plug-in-charger" else (0, 20, 40))

    if task.id in {"classify-objects", "classify-objects-by-language"}:
        categories, baskets = truth["categories"], truth["baskets"]
        if set(categories) != set(s.objects) or len(set(categories.values())) != 3 or len(set(baskets)) != 3:
            raise ValueError("requires exactly three nonempty categories and baskets")
        assignments = truth.get("assignments", {})
        if task.id.endswith("by-language") and (set(assignments) != set(categories.values()) or set(assignments.values()) != set(baskets)):
            raise ValueError("language category-to-basket mapping is required")
        completed = set()
        for basket in baskets:
            contained = {o for o, fact in e.objects.items() if fact.get("container") == basket}
            for category in set(categories.values()):
                members = {o for o, c in categories.items() if c == category}
                if task.id.endswith("by-language") and assignments[category] != basket:
                    continue
                if contained == members and all(valid(o, "settled") for o in members):
                    completed.add(category)
        return levels(len(completed), 3, (0, 10 if task.id.endswith("by-language") else 15, 40))

    if task.id == "play-stacking-toy":
        groups, pegs = truth["groups"], truth["pegs"]
        if set(groups) != set(s.objects) or sorted(list(groups.values()).count(g) for g in set(groups.values())) != [1, 2, 3, 4]:
            raise ValueError("stacking toy groups must have sizes 4, 3, 2, 1")
        if set(pegs) != set(groups.values()) or len(set(pegs.values())) != 4:
            raise ValueError("each shape group needs a distinct peg")
        n = sum(all(e.objects[o].get("container") == pegs[g] and valid(o, "at_base", "aligned", "settled")
                    for o in s.objects if groups[o] == g) for g in pegs)
        return levels(n, 4, (0, 10, 30, 60))

    if task.id == "align-blocks":
        success = home and all(e.flags.get(k) is True for k in ("alignment_valid", "no_lift_entire_episode", "used_set_square"))
        return Score(100 if success else 0, success, int(success))
    raise ValueError(f"unimplemented task: {task.id}")
