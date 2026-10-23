"""Shared SE3 XPolicyLab entry point for native GaP and CaP deployments.

Deployments receive SE3Env directly: get_obs, take_action, is_episode_end.
No task solver, synthetic evidence, or motion defaults are supplied here.
"""
import math
from dataclasses import replace
from pathlib import Path
import json
import numpy as np


def run_deployment(deploy, model_client, *, harness, task, start_pose,
                   frequency, output, station_id="se3-labs-yam-2",
                   address="100.107.161.92:7443", episode_timeout_s=450,
                   evaluate=None):
    """Run one operator-confirmed episode and retain the actual score sheet.

    The native deployment owns model reset, action generation, and checking
    subsequent observations. take_action is pacing, not physical verification.
    start_pose must be a station-approved Station_JointPose, not inferred here.
    """
    if harness not in {"native-gap", "cap"}:
        raise ValueError("harness must be native-gap or cap")
    if not callable(deploy) or model_client is None:
        raise ValueError("a native deployment and model client are required")
    for name, value in (("frequency", frequency), ("episode_timeout_s", episode_timeout_s)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if episode_timeout_s > 450:
        raise ValueError("each trial is limited to 450 seconds")
    from se3labs.interface.eval.repository import Bimanual_YAM_Station
    from se3labs.interface.eval.station import Station_JointPose
    if not isinstance(start_pose, Station_JointPose):
        raise ValueError("an explicit station-approved start pose is required")
    start_pose.validate(Bimanual_YAM_Station)
    if frequency > min(arm.control_rate for arm in Bimanual_YAM_Station.arms.values()):
        raise ValueError("frequency exceeds YAM station control rate")
    if any(not np.isfinite(p.joint_angle_q).all() or not np.isfinite(p.gripper_pos).all()
           for p in start_pose.arms.values()):
        raise ValueError("start pose contains non-finite positions")
    task = replace(task, max_rollout_time=episode_timeout_s)
    if evaluate is None:
        from se3labs.sdk.bridge.xpolicylab import evaluate
    from google.protobuf.json_format import MessageToDict
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {"bridge": "se3labs.sdk.bridge.xpolicylab.evaluate",
                "harness": harness, "station_id": station_id,
                "episode_timeout_s": episode_timeout_s, "frequency": frequency,
                "episodes": 1, "task": task.name}
    (folder / "deployment.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    try:
        report = evaluate(deploy, model_client, station_id=station_id, address=address,
                          task=task, start_pose=start_pose, frequency=frequency, episodes=1)
    except BaseException as exc:
        (folder / "failure.json").write_text(json.dumps({"error_type": type(exc).__name__}), encoding="utf-8")
        raise
    result = {"state": report.state, "close_reason": report.close_reason,
              "episodes": report.episodes, "steps": report.steps,
              "error_count": len(report.errors),
              "results": [MessageToDict(r, preserving_proto_field_name=True) for r in report.results]}
    (folder / "se3-session.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return report
