import argparse, json, os
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
import numpy as np
import imageio.v2 as iio
from PIL import Image, ImageDraw, ImageFont


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    p.add_argument("--diagnostic", action="store_true")
    a = p.parse_args()
    names = ["diagnostic"] if a.diagnostic else ["A", "B"]
    records = []
    for s in names:
        f = a.run / s
        m = mujoco.MjModel.from_xml_path(str(f / "scene.xml"))
        d = mujoco.MjData(m)
        m.vis.global_.offwidth = 720
        m.vis.global_.offheight = 640
        rows = [json.loads(x) for x in (f / "trajectory.jsonl").read_text().splitlines()]
        records.append(
            (s, m, d, mujoco.Renderer(m, height=640, width=720), rows, json.loads((f / "summary.json").read_text()))
        )
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0.21, 0, 0.20]
    camera.distance = 1.05
    camera.azimuth = 135
    camera.elevation = -23
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 19)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    writer = iio.get_writer(a.run / "moving-cube-comparison.mp4", fps=20, codec="libx264", quality=9)
    duration = max(r[-2][-1]["wall_s"] for r in records)
    if all(r[-1]["success"] for r in records):
        duration = min(duration, max(r[-1]["success_s"] for r in records) + 2)
    try:
        for t in np.arange(0, duration, 0.05):
            panels = []
            for s, m, d, renderer, rows, summary in records:
                row = rows[max(0, np.searchsorted([r["wall_s"] for r in rows], t, side="right") - 1)]
                d.qpos[:] = row["qpos"]
                mujoco.mj_forward(m, d)
                renderer.update_scene(d, camera=camera)
                im = Image.fromarray(renderer.render().copy())
                draw = ImageDraw.Draw(im)
                draw.rectangle((0, 0, 720, 86), fill=(18, 31, 39))
                label = {
                    "A": "A · Native GaP + Astra",
                    "B": "B · GaP + Jev + custom Rust executor",
                    "diagnostic": "Local controller development",
                }[s]
                if summary.get("diagnostic") and s in {"A", "B"}:
                    label = {
                        "A": "A · Native GaP + local test worker",
                        "B": "B · GaP + custom Rust executor + local test worker",
                    }[s]
                draw.text((18, 12), label, font=font, fill="white")
                stamp = summary["success_s"]
                done = stamp is not None and t >= stamp
                text = (
                    f"Elapsed: {t:05.2f}s   |   Pickup: "
                    + (f"{stamp:.2f}s" if done else "—")
                    + f"   |   {row['phase']}"
                )
                draw.text((18, 48), text, font=small, fill=(174, 225, 217))
                panels.append(np.array(im))
            frame = np.concatenate(panels, axis=1)
            writer.append_data(frame)
            if any(abs(t - x) < 0.001 for x in [1, 2, 3, 5, 8]):
                Image.fromarray(frame).save(a.run / f"frame-{t:.0f}.png")
    finally:
        writer.close()
        for r in records:
            r[3].close()


if __name__ == "__main__":
    main()
