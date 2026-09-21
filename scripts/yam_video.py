"""Render recorded MuJoCo trajectories; matched wall-time 1x playback."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
import numpy as np
import imageio.v2 as iio
from PIL import Image, ImageDraw, ImageFont


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--condition", default="early")
    args = p.parse_args()
    config = json.loads((args.run / "config.json").read_text())
    captures = []
    for system in ["A", "B"]:
        folder = args.run / f"{system}-{args.seed}-{args.condition}"
        rows = [json.loads(x) for x in (folder / "trajectory.jsonl").read_text().splitlines()]
        model = mujoco.MjModel.from_xml_path(str(folder / "scene.xml"))
        data = mujoco.MjData(model)
        target = mujoco.MjData(model)
        render = mujoco.Renderer(model, height=480, width=640)
        captures.append((system, rows, model, data, target, render))
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0.1, 0, 0.4]
    camera.distance = 1.9
    camera.azimuth = 135
    camera.elevation = -22
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    output = args.run / f"paired-{args.seed}-{args.condition}.mp4"
    writer = iio.get_writer(output, fps=20, codec="libx264", quality=8)
    try:
        for t in np.arange(0, config["duration_s"], 0.05):
            panels = []
            for system, rows, model, data, target, render in captures:
                row = rows[max(0, np.searchsorted([r["wall_s"] for r in rows], t, side="right") - 1)]
                data.qpos[:] = row["qpos"]
                mujoco.mj_forward(model, data)
                target.qpos[:] = row["qpos"]
                target.qpos[:6] = row["target"]
                mujoco.mj_forward(model, target)
                render.update_scene(data, camera=camera)
                scn = render.scene
                pos = target.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "gripper")]
                mujoco.mjv_initGeom(
                    scn.geoms[scn.ngeom],
                    mujoco.mjtGeom.mjGEOM_SPHERE,
                    np.array([0.018, 0.018, 0.018]),
                    pos,
                    np.eye(3).flatten(),
                    np.array([0.9, 0.2, 0.1, 0.65]),
                )
                scn.ngeom += 1
                img = Image.fromarray(render.render().copy())
                d = ImageDraw.Draw(img)
                d.rectangle((0, 0, 640, 92), fill=(18, 31, 39))
                label = "Native GaP + Astra" if system == "A" else "GaP workflow / Rust + Jev"
                if config["diagnostic"]:
                    label = system + " executor · deterministic test worker"
                d.text((12, 9), label, font=font, fill="white")
                d.text(
                    (12, 34),
                    f"Wall {t:.2f}s | physics {row['sim_s']:.2f}s | scene {row['scene_version']}",
                    font=font,
                    fill="white",
                )
                d.text(
                    (12, 59),
                    f"Max joint error {row['error_rad']:.3f} rad | target: red marker",
                    font=font,
                    fill="white",
                )
                panels.append(np.array(img))
            frame = np.concatenate(panels, axis=1)
            img = Image.fromarray(frame)
            d = ImageDraw.Draw(img)
            d.rectangle((0, 452, 1280, 480), fill=(18, 31, 39))
            label = "DIAGNOSTIC ONLY · no live models" if config["diagnostic"] else "SIMULATION PILOT · no hardware"
            d.text(
                (12, 455),
                f"{label} | recorded physics trajectories | synchronized 1x wall-time playback | {args.condition}",
                font=font,
                fill="white",
            )
            writer.append_data(np.array(img))
            if abs(t - 2.5) < 0.001:
                img.save(args.run / f"preview-{args.condition}.png")
    finally:
        writer.close()
        for item in captures:
            item[-1].close()
    print(str(output))


if __name__ == "__main__":
    main()
