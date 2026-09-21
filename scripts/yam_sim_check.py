"""Official YAM SDK smoke test. This script has no physical-robot mode."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

os.environ.setdefault("MUJOCO_GL", "egl")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/i2rt"))
import mujoco
import numpy as np
import imageio.v2 as iio
from PIL import Image, ImageDraw, ImageFont
from i2rt.robots.get_robot import get_yam_robot
from i2rt.robots.sim_robot import SimRobot
from i2rt.robots.utils import ArmType, GripperType


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    # An unexpected SDK path must not silently connect to a CAN interface.
    from unittest.mock import patch

    with patch(
        "i2rt.motor_drivers.can_interface.CanInterface.__init__",
        side_effect=AssertionError("CAN forbidden in simulation check"),
    ):
        robot = get_yam_robot(arm_type=ArmType.YAM, gripper_type=GripperType.LINEAR_4310, sim=True)
    assert isinstance(robot, SimRobot)
    tree = ET.parse(robot.xml_path)
    root = tree.getroot()
    wb = root.find("worldbody")
    ET.SubElement(wb, "light", pos="0 -1 2", dir="0 0 -1", diffuse=".8 .8 .8")
    ET.SubElement(wb, "light", pos="1 1 1", dir="-1 -1 -1", diffuse=".5 .5 .5")
    ET.SubElement(wb, "geom", name="demo_floor", type="plane", size="2 2 .02", pos="0 0 -.025", rgba=".85 .88 .9 1")
    visual = root.find("visual")
    if visual is None:
        visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "global", offwidth="960", offheight="720")
    scene = args.output / "yam_viewer_scene.xml"
    tree.write(scene)
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0.10, 0, 0.32]
    camera.distance = 1.65
    camera.azimuth = 135
    camera.elevation = -22
    renderer = mujoco.Renderer(model, height=720, width=960)
    writer = iio.get_writer(args.output / "yam-simulation.mp4", fps=30, codec="libx264", quality=8)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    timings = []
    errors = []
    checks = {
        "sim_instance": True,
        "dofs": robot.num_dofs(),
        "frames": 180,
        "can_attempts": 0,
        "observation_keys": list(robot.get_observations()),
        "finite_state": True,
    }
    try:
        for i in range(180):
            t = i / 30
            q = np.array(
                [
                    0.35 * np.sin(t),
                    1.0 + 0.25 * np.sin(t),
                    1.7 + 0.25 * np.sin(t + 0.4),
                    -0.4 + 0.2 * np.sin(t + 0.8),
                    0.25 * np.sin(t),
                    0.3 * np.sin(t),
                    0.5 + 0.45 * np.sin(t),
                ]
            )
            begin = time.monotonic_ns()
            robot.command_joint_pos(q)
            obs = robot.get_observations()
            timings.append((time.monotonic_ns() - begin) / 1e6)
            actual = robot.get_joint_pos()
            errors.append(float(np.max(np.abs(q - actual))))
            assert np.isfinite(actual).all()
            data.qpos[:] = robot._data.qpos
            mujoco.mj_forward(model, data)
            renderer.update_scene(data, camera=camera)
            frame = renderer.render().copy()
            assert frame.std() > 5, "Blank renderer output"
            image = Image.fromarray(frame)
            d = ImageDraw.Draw(image)
            d.rectangle((0, 0, 960, 74), fill=(15, 34, 39))
            d.text((18, 10), "OFFICIAL YAM MODEL + LINEAR 4310 GRIPPER", font=font, fill="white")
            d.text(
                (18, 40),
                f"SIMULATION ONLY | SDK kinematic check | no CAN | t = {t:.2f}s",
                font=font,
                fill=(171, 224, 213),
            )
            writer.append_data(np.array(image))
            if i == 90:
                image.save(args.output / "preview.png")
    finally:
        writer.close()
        renderer.close()
        robot.close()
    checks.update(
        {
            "max_command_readback_error": max(errors),
            "sdk_command_and_read_ms": {
                "p50": float(np.percentile(timings, 50)),
                "p95": float(np.percentile(timings, 95)),
            },
            "i2rt_commit": subprocess.check_output(
                ["git", "-C", str(ROOT / "vendor/i2rt"), "rev-parse", "HEAD"], text=True
            ).strip(),
            "mujoco_version": mujoco.__version__,
            "scope": "SDK/model installation check. Kinematic position updates, not contact-rich grasp dynamics, GaP/Rust/Jev performance, or hardware validation.",
        }
    )
    (args.output / "summary.json").write_text(json.dumps(checks, indent=2))
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
