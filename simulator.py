"""Execute one candidate in an independent simulation; stream top_cam to MP4."""
from pathlib import Path
from uuid import uuid4
import json
import os
import sys

# Set before importing MuJoCo; callers may explicitly choose EGL instead.
if sys.platform.startswith('linux'):
    os.environ.setdefault('MUJOCO_GL', 'osmesa')

import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image
from actions import Robot, SCENE, PARTS
from planner import validate

BINS = ('bin_a', 'bin_b')
RUNS = Path(__file__).resolve().parent / 'runs'


def check_goals(robot, goals):
    """Require each entire cube inside its requested bin, below the walls, released.

    Bounds come from the scene's five box geoms in bin-local coordinates.
    This also handles translated/rotated bins and rotated cubes.
    """
    for part, bin_name in goals.items():
        if robot.held == part:
            return False, f'{part} is still held'
        model, data = robot.model, robot.data
        body = model.body(bin_name)
        ids = range(body.geomadr[0], body.geomadr[0] + body.geomnum[0])
        boxes = [g for g in ids if model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX]
        if len(boxes) != 5:
            raise ValueError(f'{bin_name} must have one floor and four box walls')
        floor = min(boxes, key=lambda g: model.geom_pos[g, 2] + model.geom_size[g, 2])
        walls = [g for g in boxes if g != floor]
        bounds = []
        for axis in (0, 1):
            faces = sorted(model.geom_pos[g, axis] + (model.geom_size[g, axis] if model.geom_pos[g, axis] < 0 else -model.geom_size[g, axis])
                           for g in walls if abs(model.geom_pos[g, axis]) > 1e-8)
            if len(faces) != 2:
                raise ValueError(f'{bin_name} needs axis-aligned walls in its local frame')
            bounds.append(faces)
        bottom = model.geom_pos[floor, 2] + model.geom_size[floor, 2]
        top = min(model.geom_pos[g, 2] + model.geom_size[g, 2] for g in walls)
        geom = model.geom(f'{part}_geom').id
        signs = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])
        corners = (signs * model.geom_size[geom]) @ data.geom_xmat[geom].reshape(3, 3).T + data.geom_xpos[geom]
        local = (corners - data.body(bin_name).xpos) @ data.body(bin_name).xmat.reshape(3, 3)
        if any(np.min(local[:, axis]) < lo - .001 or np.max(local[:, axis]) > hi + .001
               for axis, (lo, hi) in enumerate(bounds)) or np.min(local[:, 2]) < bottom - .002 or np.max(local[:, 2]) >= top:
            return False, f'{part} is not inside {bin_name}'
    return True, ''


class Recorder:
    def __init__(self, robot, renderer, writer, fps):
        self.robot, self.renderer, self.writer = robot, renderer, writer
        self.fps, self.next_frame = fps, float(robot.data.time)
        self.collisions = 0
        self.dropped = False
        self.active_contacts = set()
        self.action = None
        self.carried = None
        model = robot.model
        self.table = model.geom('table').id
        base = model.body('link0').id
        self.arm = set()
        for body in range(model.nbody):
            ancestor = body
            while ancestor and ancestor != base:
                ancestor = int(model.body_parentid[ancestor])
            if ancestor == base and body != base:
                self.arm.add(body)

    def frame(self):
        self.renderer.update_scene(self.robot.data, camera='top_cam')
        return self.renderer.render()

    def observe(self, robot):
        contacts = set()
        for contact in robot.data.contact:
            a, b = int(contact.geom1), int(contact.geom2)
            other = b if a == self.table else a if b == self.table else None
            if other is not None and int(robot.model.geom_bodyid[other]) in self.arm:
                contacts.add(other)
        # Count contact episodes, not the same resting contact every physics tick.
        self.collisions += len(contacts - self.active_contacts)
        self.active_contacts = contacts
        if self.action == 'grasp' and self.carried is None:
            for part in PARTS:
                if robot._finger_contacts(part):
                    self.carried = part
                    break
        if self.action != 'release':
            self.carried = robot.held or self.carried
        if self.carried is not None and np.linalg.norm(robot.data.body(self.carried).xpos - robot.tcp) > .06:
            self.dropped = True
        if robot.data.time + 1e-9 >= self.next_frame:
            self.writer.append_data(self.frame())
            self.next_frame += 1 / self.fps


def run_plan(plan, goals=None, run_dir=None, *, scene=SCENE, fps=30, video_size=(640, 480)):
    """Run a plan against explicit {part: bin} goals; return JSON-safe measurements.

    Each call owns its robot, renderer, encoder and unique candidate subfolder.
    failed_step is one-based. time excludes Robot's initial settling period.
    """
    result = dict(plan_id=plan.get('plan_id') if isinstance(plan, dict) else None,
                  success=False, steps_done=0, time=0., collisions=0, dropped=False,
                  failed_step=None, reason='', image_path=None, video_path=None)
    ok, reason = validate(plan)
    if not ok:
        result['reason'] = reason
        return result
    if not isinstance(goals, dict) or not goals or any(p not in PARTS or b not in BINS for p, b in goals.items()):
        result['reason'] = 'goals must map requested parts to bin_a or bin_b'
        return result
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 60:
        result['reason'] = 'fps must be an integer from 1 to 60'
        return result
    folder = Path(run_dir or RUNS) / f'candidate-{uuid4().hex}'
    folder.mkdir(parents=True)
    robot = recorder = None
    start = 0.
    try:
        robot = Robot(scene=scene)
        start = float(robot.data.time)
        video = folder / 'video.mp4'
        width, height = video_size
        with mujoco.Renderer(robot.model, width=width, height=height) as renderer:
            with imageio.get_writer(video, fps=fps, codec='libx264', pixelformat='yuv420p', macro_block_size=1) as writer:
                recorder = Recorder(robot, renderer, writer, fps)
                robot.step_callback = recorder.observe
                recorder.observe(robot)
                for n, step in enumerate(plan['steps'], 1):
                    recorder.action = step['action']
                    if recorder.action == 'release':
                        # Intentional release is not a dropped part.
                        recorder.carried = None
                        recorder.action = 'release'
                    values = (step['target'],) if step['action'] == 'move_to' else (step['height'],) if 'height' in step else ()
                    outcome = getattr(robot, step['action'])(*values)
                    if not outcome['ok']:
                        result.update(failed_step=n, reason=outcome['reason'])
                        break
                    result['steps_done'] += 1
                recorder.action = None
                robot._deadline = robot.data.time + 1.01
                robot._wait(1.)
            result['video_path'] = str(video.resolve())
        with mujoco.Renderer(robot.model, width=1280, height=960) as renderer:
            renderer.update_scene(robot.data, camera='top_cam')
            image = folder / 'final.png'
            Image.fromarray(renderer.render()).save(image)
            result['image_path'] = str(image.resolve())
        if result['failed_step'] is None:
            passed, reason = check_goals(robot, goals)
            result.update(success=passed and recorder.collisions == 0 and not recorder.dropped,
                          reason='arm hit the table' if recorder.collisions else 'part dropped before release' if recorder.dropped else reason)
    except Exception as exc:
        result.update(success=False, reason=f'simulation failed: {exc}')
    finally:
        if robot is not None:
            robot.step_callback = None
            result['time'] = round(float(robot.data.time) - start, 6)
        if recorder is not None:
            result.update(collisions=recorder.collisions, dropped=recorder.dropped)
    (folder / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
