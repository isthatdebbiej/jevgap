"""Known red-cube RGB-D detector, not a general perception model."""

import mujoco
import numpy as np


def estimate_cube(rgb, depth, camera_position, camera_rotation, fovy):
    image = rgb.astype(float)
    mask = (image[:, :, 0] > 80) & (image[:, :, 0] > 1.7 * image[:, :, 1]) & (image[:, :, 0] > 1.7 * image[:, :, 2])
    ys, xs = np.where(mask & np.isfinite(depth) & (depth > 0))
    if len(xs) < 12:
        return None, 0.0
    h, w = depth.shape
    focal = 0.5 * h / np.tan(np.deg2rad(fovy) / 2)
    z = depth[ys, xs]
    local = np.stack([(xs + 0.5 - w / 2) * z / focal, -(ys + 0.5 - h / 2) * z / focal, -z], axis=1)
    surface = np.median(local @ camera_rotation.T + camera_position, axis=0)
    # Known upright 36 mm cube, viewed from an elevated camera. Validity is limited to that geometry.
    surface[2] -= 0.018
    return surface.tolist(), min(1.0, len(xs) / 100)


def camera_observation(world):
    if world.renderer is None:
        world.renderer = mujoco.Renderer(world.m, height=160, width=160)
    renderer = world.renderer
    renderer.update_scene(world.d, camera="bench_camera")
    rgb = renderer.render().copy()
    renderer.enable_depth_rendering()
    try:
        depth = renderer.render().copy()
    finally:
        renderer.disable_depth_rendering()
    camera = mujoco.mj_name2id(world.m, mujoco.mjtObj.mjOBJ_CAMERA, "bench_camera")
    return estimate_cube(
        rgb, depth, world.d.cam_xpos[camera], world.d.cam_xmat[camera].reshape(3, 3), world.m.cam_fovy[camera]
    )
