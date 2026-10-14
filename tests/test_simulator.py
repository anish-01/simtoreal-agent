import json
from types import SimpleNamespace
import imageio.v2 as imageio
import mujoco
import numpy as np
import pytest
from actions import Robot
from simulator import Recorder, check_goals, run_plan


def place(robot, part, xyz, quat=(1, 0, 0, 0)):
    adr = robot.model.joint(f'{part}_joint').qposadr[0]
    robot.data.qpos[adr:adr+7] = [*xyz, *quat]
    mujoco.mj_forward(robot.model, robot.data)


def plan(part='red_part', bin_name='bin_a'):
    return {'plan_id': 1, 'steps': [{'action': 'move_to', 'target': part},
            {'action': 'grasp'}, {'action': 'lift'}, {'action': 'move_to', 'target': bin_name},
            {'action': 'release'}, {'action': 'home'}]}


@pytest.fixture
def robot():
    return Robot()


def test_bin_geometry_and_all_goals(robot):
    robot.model.body('bin_a').pos[:2] += [.04, .03]
    mujoco.mj_forward(robot.model, robot.data)
    center = robot.data.body('bin_a').xpos.copy()
    place(robot, 'red_part', center + [0, 0, .035])
    assert check_goals(robot, {'red_part': 'bin_a'}) == (True, '')
    assert not check_goals(robot, {'red_part': 'bin_b'})[0]
    assert not check_goals(robot, {'red_part': 'bin_a', 'blue_part': 'bin_b'})[0]
    place(robot, 'blue_part', robot.data.body('bin_b').xpos + [0, 0, .035])
    assert check_goals(robot, {'red_part': 'bin_a', 'blue_part': 'bin_b'})[0]
    robot.held = 'red_part'
    assert not check_goals(robot, {'red_part': 'bin_a'})[0]


@pytest.mark.parametrize('offset', [[.07, 0, .035], [0, 0, .11], [0, 0, -.1], [.085, 0, .115]])
def test_cube_crossing_wall_or_above_or_below_bin_fails(robot, offset):
    place(robot, 'red_part', robot.data.body('bin_a').xpos + offset)
    assert not check_goals(robot, {'red_part': 'bin_a'})[0]


def test_rotated_bin_and_cube(robot):
    robot.model.body('bin_a').quat[:] = [np.cos(.2), 0, 0, np.sin(.2)]
    mujoco.mj_forward(robot.model, robot.data)
    place(robot, 'red_part', robot.data.body('bin_a').xpos + [0, 0, .035], [np.cos(.1), 0, 0, np.sin(.1)])
    assert check_goals(robot, {'red_part': 'bin_a'})[0]


@pytest.mark.parametrize('goals', [None, {}, {'red_part': 'unknown'}, {'unknown': 'bin_a'}])
def test_missing_or_bad_goals_fail(tmp_path, goals):
    result = run_plan(plan(), goals, tmp_path)
    assert not result['success'] and 'goals' in result['reason']
    assert not list(tmp_path.iterdir())


def test_bad_plan_fails_before_simulation(tmp_path):
    result = run_plan({'steps': [{'action': 'delete'}]}, {'red_part': 'bin_a'}, tmp_path)
    assert not result['success'] and result['steps_done'] == 0
    assert result['video_path'] is None


def test_contact_episodes_and_drop_measurements(robot):
    recorder = Recorder(robot, None, None, 30)
    recorder.next_frame = float('inf')
    table = robot.model.geom('table').id
    arm_geom = robot.model.body('link1').geomadr[0]
    base_geom = robot.model.body('link0').geomadr[0]
    fake = SimpleNamespace(model=robot.model, data=SimpleNamespace(contact=[SimpleNamespace(geom1=table, geom2=arm_geom)], time=0), held=None)
    recorder.observe(fake)
    recorder.observe(fake)
    assert recorder.collisions == 1
    fake.data.contact = []
    recorder.observe(fake)
    fake.data.contact = [SimpleNamespace(geom1=base_geom, geom2=table)]
    recorder.observe(fake)
    assert recorder.collisions == 1
    fake.data.contact = [SimpleNamespace(geom1=arm_geom, geom2=table)]
    recorder.observe(fake)
    assert recorder.collisions == 2
    robot.held = 'red_part'
    recorder.observe(robot)
    assert recorder.dropped


@pytest.mark.parametrize('part,bin_name', [('red_part', 'bin_a'), ('blue_part', 'bin_b')])
def test_physical_plan_and_decodable_media(tmp_path, part, bin_name):
    result = run_plan(plan(part, bin_name), {part: bin_name}, tmp_path, fps=10, video_size=(320, 240))
    assert result['success'], result
    assert result['steps_done'] == 6 and result['time'] > 1
    assert result['collisions'] == 0 and not result['dropped']
    assert imageio.imread(result['image_path']).shape == (960, 1280, 3)
    with imageio.get_reader(result['video_path']) as reader:
        assert reader.get_data(0).shape == (240, 320, 3)
        frames = reader.count_frames()
        assert abs(frames - result['time'] * 10) <= 2
    stored = json.loads((__import__('pathlib').Path(result['image_path']).parent / 'result.json').read_text())
    assert stored == result


def test_wrong_bin_and_release_on_table(tmp_path):
    wrong = run_plan(plan(bin_name='bin_b'), {'red_part': 'bin_a'}, tmp_path, fps=5, video_size=(160, 120))
    assert not wrong['success'] and 'not inside bin_a' in wrong['reason']
    table = plan()
    table['steps'] = table['steps'][:3] + [{'action': 'release'}]
    result = run_plan(table, {'red_part': 'bin_a'}, tmp_path, fps=5, video_size=(160, 120))
    assert not result['success'] and not result['dropped']
    assert result['image_path'] != wrong['image_path']


def test_stop_at_first_failed_action(tmp_path, monkeypatch):
    monkeypatch.setattr(Robot, 'move_to', lambda self, target: {'ok': False, 'reason': 'timeout'})
    monkeypatch.setattr(Robot, 'grasp', lambda self: pytest.fail('must not run after failure'))
    result = run_plan(plan(), {'red_part': 'bin_a'}, tmp_path, fps=5, video_size=(160, 120))
    assert result['failed_step'] == 1 and result['steps_done'] == 0
    assert result['reason'] == 'timeout' and not result['success']
    assert result['video_path'] and result['image_path']
