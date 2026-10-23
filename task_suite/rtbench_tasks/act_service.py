"""One ACT episode with the actual task rubric; never retries a station session."""
import argparse
import os
import time
from pathlib import Path

from .config import Experiment
from .act import settings, start_joints


class ACTTelemetryMixin:
    """Preserve actual sensor timestamps absent from the stock ACT status reply."""
    def infer(self, observation):
        self.observation_received_ns = time.monotonic_ns()
        return super().infer(observation)

    def reply(self, ok, message):
        result = super().reply(ok, message)
        result.update(episode_id=self.episode_id, calibration_id=self.calibration_id,
                      observation_received_ns=getattr(self, "observation_received_ns", None))
        raw = self.last_observation
        if raw is not None:
            for name, arm in raw.arms.items():
                if name in result["arms"]:
                    result["arms"][name]["measured_timestamp_s"] = float(arm.timestamp)
        return result


def serve(experiment, *, live=False):
    if live is not True:
        raise ValueError("station service requires --live")
    if os.name != "posix":
        raise ValueError("ACT requires Linux/WSL")
    if len(experiment.trials) != 1:
        raise ValueError("one ACT episode per service")
    cfg, station = settings(experiment), experiment.station_config()
    output = Path(cfg["session_report"])
    if output.exists() or Path(cfg["socket_path"]).exists():
        raise ValueError("session report and socket paths must be fresh")
    joints = start_joints(station)
    scenario = experiment.scenario(*experiment.trials[0])
    for key in ("station_id", "address", "calibration_id", "driver_factory", "driver_config"):
        if not station.get(key) or "REPLACE" in str(station[key]):
            raise ValueError(f"configure station.{key}")
    if (scenario.task_id not in station.get("validated_tasks", [])
            or not station.get("reset_instructions", {}).get(scenario.task_id)
            or scenario.layout.startswith(("UNCONFIGURED", "fixture", "replay"))):
        raise ValueError("validate the driver, physical layout and operator reset instructions first")
    # All SDK imports and physical interfaces are behind the explicit live gate.
    from se3labs.sdk.examples.act_harness.policy import ActHarnessPolicy
    from se3labs.sdk import eval_client
    from se3labs.interface.eval.job import JobRequest
    from google.protobuf.json_format import MessageToDict
    from .se3 import load_driver, SDKTypes, task_spec
    from .experiment import write_json
    driver = load_driver(station["driver_factory"], config_path=station["driver_config"],
                         calibration_id=station["calibration_id"])

    class ValidatedPolicy(ACTTelemetryMixin, ActHarnessPolicy):
        episode_id = scenario.id
        calibration_id = station["calibration_id"]
        def initialize(self, spec, task):
            driver.validate_station(spec)
            expected = SDKTypes().start_pose(station["start_pose"], spec)
            driver.validate_start_pose(expected)
            return super().initialize(spec, task)

    policy = None
    result = {"episode_id": scenario.id, "state": "FAILED", "episodes": 0,
              "error_count": 1, "results": []}
    try:
        kwargs = {key: cfg[key] for key in ("speed_m_s", "accel_m_s2", "rot_speed_deg_s",
                  "rot_accel_deg_s2", "gripper_rate", "reach_m", "snapshot_period_s", "socket_path", "snapshot_dir")}
        policy = ValidatedPolicy(keyboard=False, start_q=joints, **kwargs)
        request = JobRequest(task=task_spec(scenario, station, experiment.limits["episode_timeout_s"]),
                             policy=policy, episodes=1)
        session = eval_client.serve_policy(station["station_id"], station["address"], request)
        result.update(state=session.state, episodes=session.episodes, error_count=len(session.errors),
                      close_reason=session.close_reason,
                      results=[MessageToDict(r, preserving_proto_field_name=True) for r in session.results])
    except BaseException as exc:
        result["error_type"] = type(exc).__name__
        raise
    finally:
        try:
            if policy is not None:
                policy.close()
        finally:
            driver.close()
            temporary = output.with_name(output.name + ".pending")
            write_json(temporary, result)
            temporary.replace(output)  # Readers see only a complete session report.
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; use rtbench_tasks doctor for offline configuration checks")
    serve(Experiment(args.config), live=True)


if __name__ == "__main__":
    main()
