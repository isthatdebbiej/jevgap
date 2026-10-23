"""Precision/memory protocol, separate from the thirteen RoboDojo ports.

This module defines cues and operator scoring, not a robot controller. Only
independently verified transfer events may advance the cue schedule. Never
pass this object's private job or the scoring sheet into a policy prompt.
"""
from dataclasses import dataclass


INITIAL_JOB = (
    "After the transport jobs, place A at T2 facing 90 degrees, then C at T1 "
    "facing 0 degrees, then B at T3 facing 180 degrees. Leave A, B, and C "
    "untouched until the final execute cue. Remember this instruction; it "
    "will not be repeated."
)
DISTRACTOR_TRANSFERS = (
    ("D", "D2"), ("E", "E2"), ("D", "D1"), ("E", "E1"),
    ("D", "D2"), ("E", "E2"), ("D", "D1"), ("E", "E1"),
)


@dataclass
class CueSchedule:
    """One instance per policy episode; decision count does not advance work."""
    correction: bool = False
    initial_job: str = INITIAL_JOB
    transfers: int = 0
    initial_shown: bool = False
    correction_shown: bool = False

    def cue(self):
        if not self.initial_shown:
            self.initial_shown = True
            return self.initial_job
        if self.correction and self.transfers == 2 and not self.correction_shown:
            self.correction_shown = True
            return "Swap A's and B's destinations; preserve order and orientation."
        if self.transfers < 8:
            obj, target = DISTRACTOR_TRANSFERS[self.transfers]
            return f"Transport {obj} to {target}; release it stably."
        return "Execute the remembered job."

    def verified_transfer(self, object_id, target_id, *, verified):
        if not self.initial_shown:
            raise ValueError("initial instruction has not been delivered")
        if self.correction and self.transfers == 2 and not self.correction_shown:
            raise ValueError("deliver the correction before the third transfer")
        if verified is not True or self.transfers >= 8:
            raise ValueError("only independently verified distractor transfers advance cues")
        if (object_id, target_id) != DISTRACTOR_TRANSFERS[self.transfers]:
            raise ValueError("wrong distractor object, destination, or sequence")
        self.transfers += 1


def task_spec(*, correction=False):
    """Static SDK instruction omits the hidden job, preventing get_obs leakage.

    Physical layout and proposed measurement thresholds require commissioning.
    This Task_Spec cannot by itself run the policy or measure a transfer.
    """
    from se3labs.interface.eval.task import Task_Spec, Task_ScoreSheet, Task_ScoreItem, Task_ScoreKind
    return Task_Spec(
        name="precision-memory-correction" if correction else "precision-memory-delayed",
        description="Eight distractor transfers followed by three remembered placements.",
        reset_instruction=(
            "Use five labelled, arrow-marked cubes A, B, C, D, E. Prepare the "
            "recorded matched layout with task targets T1/T2/T3 and distractor "
            "buffers D1/D2/E1/E2. D and E start at D1/E1. Establish the recorded "
            "yaw reference and placement tolerances before collection. Confirm "
            "the scene, start pose, reachable targets, and stop control. Clear "
            "policy memory between GaP and CaP; retain the same layout."
        ),
        instruction="Follow the current episode cue. Retain hidden instructions in your own episode memory.",
        max_rollout_time=450,
        scoring=Task_ScoreSheet(
            success=Task_ScoreItem("full_success", "Were all 11 transfers completed in order, with correct final targets and yaw, stable releases, no early A/B/C moves and no manual assistance?", Task_ScoreKind.Binary),
            items=(
                Task_ScoreItem("distractors", "Were all eight D/E transfers completed in the prescribed order?", Task_ScoreKind.Binary),
                Task_ScoreItem("memory", "Were the remembered object/target/orientation choices and their order correct, including any correction?", Task_ScoreKind.Binary),
                Task_ScoreItem("precision", "Did all final placements meet the frozen centre/yaw tolerances and remain stable for two seconds after release?", Task_ScoreKind.Binary),
                Task_ScoreItem("unassisted", "Was the rollout completed without manual assistance or early task-cube movement?", Task_ScoreKind.Binary),
            ),
        ),
    )
