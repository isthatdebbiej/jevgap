"""Task semantics transcribed from RoboDojo task pages, 2026-09-30.

This is a local scoring implementation, not RoboDojo's official evaluator.
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    instruction: str
    props: tuple[str, ...]
    skills: tuple[str, ...]
    count: int
    levels: tuple[int, ...]
    note: str = ""

    @property
    def source(self):
        return f"https://robodojo-benchmark.com/doc/sim-tasks/{self.id}/"

    def public(self):
        return {**asdict(self), "source": self.source}


TASKS = {t.id: t for t in (
    Task("stack-bowls", "generalization", "Stack the three bowls together, upright and stable, then return to origin.",
         ("3 nestable bowls",), ("stack",), 3, (0, 15, 100)),
    Task("pack-objects-into-box", "generalization", "Place all four objects into the aligned box with their front sides facing left, then return to origin.",
         ("4 objects with identifiable fronts", "box"), ("place",), 4, (0, 10, 25, 50, 100)),
    Task("hang-mugs", "generalization", "Hang all three mugs on the rack, then return to origin.",
         ("3 mugs with handles", "mug rack"), ("hang",), 3, (0, 15, 40, 100)),
    Task("arrange-largest-number", "generalization", "Arrange the digit tiles in descending order from left to right on the pads; preserve valid orientation, then return to origin.",
         ("4 or 5 single-digit tiles", "ordered placement pads"), ("place",), 4, (0, 5, 15, 30, 100),
         "Five-digit variant uses 25 for three correct and 40 for four correct."),
    Task("stack-blocks", "generalization", "Stack the three differently textured blocks into a stable pile, then return to origin.",
         ("3 differently textured blocks",), ("stack",), 3, (0, 15, 100)),
    Task("cover-blocks", "memory", "Cover the three blocks from left to right. Remember their colors, then uncover red, green, blue in that order and return to origin.",
         ("red, green, blue blocks", "3 opaque covers"), ("cover", "uncover"), 3, (0, 5, 15, 30, 100)),
    Task("press-by-number", "memory", "Remember the two number cards and press the corresponding red buttons that many times; follow the configured blue-confirm protocol, then return to origin.",
         ("2 number cards", "2 red buttons", "blue confirmation button"), ("press",), 2, (0, 100),
         "BLOCKED for hardware until SE3 resolves one-confirm description versus two-confirm scoring. Scenario must explicitly select two-stage-v1 to use the scoring-table interpretation."),
    Task("plug-in-charger", "precision", "Insert the charger fully into the socket, upright, then return to origin.",
         ("unpowered dummy charger", "unpowered matching socket fixture"), ("insert",), 1, (0, 100)),
    Task("insert-tubes", "precision", "Insert all three tubes upright into the rack to the required depth, one by one, then return to origin.",
         ("3 dry empty tubes", "tube rack"), ("insert",), 3, (0, 20, 40, 100)),
    Task("classify-objects", "long-horizon", "Sort all objects into three baskets by category, with one category per basket and no mixing, then return to origin.",
         ("objects from 3 categories", "3 baskets"), ("place",), 0, (0, 15, 40, 100)),
    Task("play-stacking-toy", "long-horizon", "Place every shape on its matching peg and insert each group to the base, then return to origin.",
         ("4 pegs", "4, 3, 2, 1 pieces of the corresponding shapes"), ("insert",), 10, (0, 10, 30, 60, 100)),
    Task("align-blocks", "open", "Use the set square to push three blocks into a straight, parallel aligned row without lifting the blocks, then return to origin.",
         ("3 blocks", "set square"), ("push",), 3, (0, 100),
         "Requires continuous height evidence, alignment tolerances, and verified set-square use; pick-and-place is not equivalent."),
    Task("classify-objects-by-language", "open", "Place each of the three categories into the left, middle or right basket specified by the episode instruction, then return to origin.",
         ("unseen objects from 3 categories", "3 ordered baskets"), ("place",), 0, (0, 10, 40, 100)),
)}

# Common semantic commands. The adapter owns grasp planning and motion control.
SKILLS = {
    "place": "Grasp an object and place it into a container or onto a pad; honor orientation.",
    "stack": "Grasp an object and stack it on the named supporting object.",
    "hang": "Grasp a mug and hang its handle on the named rack hook.",
    "cover": "Move an opaque cover over the named block.",
    "uncover": "Remove the named cover to its parking target.",
    "press": "Press one named button once; confirmation is a separate button press.",
    "insert": "Grasp an object and insert it into the named socket, slot or peg.",
    "push": "Use the named set square to push blocks toward the target row; do not lift blocks.",
    "home": "Return to the adapter's calibrated origin after releasing objects.",
    "finish": "End the episode and request independent scoring.",
    "abort": "End the episode without further motion.",
}


def catalog(task_id):
    task = TASKS[task_id]
    return {k: SKILLS[k] for k in (*task.skills, "home", "finish", "abort")}
