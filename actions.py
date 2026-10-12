"""Bounded Panda actions. One Robot owns one independent MuJoCo simulation."""
from functools import wraps
from pathlib import Path
import math
import mink
import mujoco
import numpy as np

SCENE = Path(__file__).resolve().parent / 'scenes' / 'factory.xml'
HOME = np.array([0, 0, 0, -1.57079, 0, 1.57079, -0.7853])
PARTS = ('red_part', 'blue_part')
TARGETS = PARTS + ('bin_a', 'bin_b')

class ActionFailure(Exception):
    pass

def action(method):
    """A single deadline covers every stage of a public action."""
    @wraps(method)
    def bounded(self, *args, **kwargs):
        self._deadline = float(self.data.time) + self.timeout
        if method.__name__ != 'grasp':
            self._hover = None
        try:
            method(self, *args, **kwargs)
            return {'ok': True, 'reason': ''}
        except ActionFailure as exc:
            self._hover = None
            return {'ok': False, 'reason': str(exc)}
        except Exception as exc:
            self._hover = None
            return {'ok': False, 'reason': f'{method.__name__} failed: {exc}'}
    return bounded

class Robot:
    def __init__(self, scene=SCENE, timeout=4.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be positive and finite')
        self.timeout = float(timeout)
        self.model = mujoco.MjModel.from_xml_path(str(scene))
        self.data = mujoco.MjData(self.model)
        # No free cubes in IK: only arm angles are sent to the physics model.
        self.ik_model = mujoco.MjModel.from_xml_path(str(SCENE.parent / 'panda' / 'panda.xml'))
        self.configuration = mink.Configuration(self.ik_model)
        self.arm_q = np.array([self.model.joint(f'joint{i}').qposadr[0] for i in range(1, 8)])
        self.arm_u = np.array([self.model.actuator(f'actuator{i}').id for i in range(1, 8)])
        self.gripper_u = self.model.actuator('actuator8').id
        self.finger_q = np.array([self.model.joint(f'finger_joint{i}').qposadr[0] for i in (1, 2)])
        self.tcp_id = self.model.site('tcp').id
        self.data.qpos[self.arm_q] = HOME
        self.data.qpos[self.finger_q] = .04
        self.data.ctrl[self.arm_u] = HOME
        self.data.ctrl[self.gripper_u] = 255
        mujoco.mj_forward(self.model, self.data)
        self.task = mink.FrameTask('tcp', 'site', 1., 1., lm_damping=1.)
        self.rotation = mink.SO3.from_matrix(np.diag([1., -1., -1.]))
        self._hover = None
        self.held = None
        self._deadline = self.data.time + 1.
        self._wait(.3)

    @property
    def tcp(self):
        return self.data.site_xpos[self.tcp_id].copy()

    def _step(self):
        if self.data.time + self.model.opt.timestep > self._deadline + 1e-9:
            raise ActionFailure('timeout')
        mujoco.mj_step(self.model, self.data)
        if not np.isfinite(self.data.qpos).all():
            raise ActionFailure('non-finite simulation state')

    def _wait(self, seconds):
        end = self.data.time + seconds
        while self.data.time < end - 1e-9:
            self._step()

    def _move(self, goal):
        goal = np.asarray(goal, dtype=float)
        if goal.shape != (3,) or not np.isfinite(goal).all():
            raise ActionFailure('invalid position')
        if np.linalg.norm(goal) > .85 or goal[2] < .015:
            raise ActionFailure('could not reach target')
        start = self.tcp
        duration = max(.25, np.linalg.norm(goal - start) / .35)
        begin = float(self.data.time)
        while True:
            progress = min(1., (self.data.time - begin) / duration)
            desired = start + (goal - start) * progress
            self.configuration.update(np.r_[self.data.qpos[self.arm_q], self.data.qpos[self.finger_q]])
            self.task.set_target(mink.SE3.from_rotation_and_translation(self.rotation, desired))
            velocity = mink.solve_ik(self.configuration, [self.task], .01, 'daqp', damping=1e-3)
            self.configuration.integrate_inplace(velocity, .01)
            self.data.ctrl[self.arm_u] = self.configuration.q[:7]
            for _ in range(5):
                self._step()
            if progress == 1. and np.linalg.norm(self.tcp - goal) < .008:
                return
            if progress == 1. and self.data.time - begin > duration + .8:
                if np.linalg.norm(self.tcp - goal) <= .02:
                    return
                raise ActionFailure('could not reach target')

    @action
    def move_to(self, target):
        if not isinstance(target, str) or target not in TARGETS:
            raise ActionFailure(f'unknown target: {target}')
        position = self.data.body(target).xpos.copy()
        position[2] += .10 if target in PARTS else .20
        self._move(position)
        self._hover = target if target in PARTS else None

    def _finger_contacts(self, part):
        part_id = self.model.body(part).id
        fingers = {self.model.body(n).id for n in ('left_finger', 'right_finger')}
        touching = set()
        for contact in self.data.contact:
            bodies = {int(self.model.geom_bodyid[contact.geom1]), int(self.model.geom_bodyid[contact.geom2])}
            if part_id in bodies:
                touching.update(bodies & fingers)
        return touching == fingers

    @action
    def grasp(self):
        part = self._hover
        self._hover = None
        if part not in PARTS or self.held is not None:
            raise ActionFailure('grasp requires hovering over an unheld part')
        before = self.data.body(part).xpos.copy()
        if np.linalg.norm(self.tcp - (before + [0, 0, .10])) > .02:
            raise ActionFailure('grasp requires hovering over a part')
        self.data.ctrl[self.gripper_u] = 255
        self._wait(.15)
        self._move(before + [0, 0, -.003])
        self.data.ctrl[self.gripper_u] = 0
        self._wait(.4)
        if not self._finger_contacts(part) or np.min(self.data.qpos[self.finger_q]) < .005:
            raise ActionFailure('nothing caught between the fingers')
        self._move(before + [0, 0, .10])
        self._wait(.1)
        after = self.data.body(part).xpos
        if after[2] - before[2] < .05 or np.linalg.norm(after - self.tcp) > .05 or not self._finger_contacts(part):
            raise ActionFailure('part did not lift with the gripper')
        self.held = part

    @action
    def release(self):
        self.data.ctrl[self.gripper_u] = 255
        self._wait(.4)
        if np.min(self.data.qpos[self.finger_q]) < .035:
            raise ActionFailure('gripper could not open')
        self.held = None

    @action
    def lift(self, height=.15):
        if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or height <= 0:
            raise ActionFailure('height must be a positive finite number')
        self._move(self.tcp + [0, 0, height])

    @action
    def home(self):
        start = self.data.qpos[self.arm_q].copy()
        begin = float(self.data.time)
        while True:
            fraction = min(1., (self.data.time - begin) / 1.5)
            self.data.ctrl[self.arm_u] = start + (HOME - start) * fraction
            self._step()
            if fraction == 1. and np.max(np.abs(self.data.qpos[self.arm_q] - HOME)) < .02:
                return
