import numpy as np
import pytest
from actions import HOME, Robot

@pytest.fixture
def robot():
    return Robot()

@pytest.mark.parametrize('part,bin_name', [('red_part','bin_a'),('blue_part','bin_b')])
def test_physical_pick_and_place(robot, part, bin_name):
    initial = robot.data.body(part).xpos.copy()
    for name,args in [('move_to',(part,)),('grasp',()),('lift',()),('move_to',(bin_name,)),('release',()),('home',())]:
        start = robot.data.time
        result = getattr(robot,name)(*args)
        assert result == {'ok':True,'reason':''}, (name,result)
        assert robot.data.time - start <= 4.000001
        if name == 'grasp':
            assert robot.data.body(part).xpos[2] > initial[2] + .05
            assert robot._finger_contacts(part)
    final = robot.data.body(part).xpos
    center = robot.data.body(bin_name).xpos
    assert np.max(np.abs(final[:2] - center[:2])) < .055
    assert .02 < final[2] < .06
    assert np.max(np.abs(robot.data.qpos[robot.arm_q]-HOME)) < .02

@pytest.mark.parametrize('target', ['missing', None, [], 1])
def test_unknown_targets_do_not_move(robot,target):
    before=robot.data.qpos.copy(); t=robot.data.time
    assert robot.move_to(target)['ok'] is False
    np.testing.assert_array_equal(robot.data.qpos,before)
    assert robot.data.time == t

def test_out_of_reach_named_part(robot):
    robot.data.qpos[robot.model.joint('red_part_joint').qposadr[0]] = 5.
    import mujoco
    mujoco.mj_forward(robot.model,robot.data)
    assert robot.move_to('red_part') == {'ok':False,'reason':'could not reach target'}

@pytest.mark.parametrize('name,args', [('move_to',('red_part',)),('grasp',()),('lift',(.05,)),('release',()),('home',())])
def test_every_action_obeys_shared_deadline(robot,name,args):
    if name=='grasp':
        assert robot.move_to('red_part')['ok']
    robot.timeout=.02
    t=robot.data.time
    assert getattr(robot,name)(*args) == {'ok':False,'reason':'timeout'}
    assert robot.data.time-t <= .0200001

def test_grasp_requires_hover(robot):
    assert not robot.grasp()['ok']
    assert robot.move_to('bin_a')['ok']
    assert not robot.grasp()['ok']

def test_empty_grasp_fails(robot):
    assert robot.move_to('red_part')['ok']
    # Remove the cube vertically without changing the remembered pickup XY.
    adr=robot.model.joint('red_part_joint').qposadr[0]
    robot.data.qpos[adr+2]=-1
    import mujoco
    mujoco.mj_forward(robot.model,robot.data)
    assert not robot.grasp()['ok']

@pytest.mark.parametrize('height', [-1,0,float('nan'),float('inf'),'high',True,5])
def test_bad_lifts_fail_cleanly(robot,height):
    assert not robot.lift(height)['ok']

def test_solver_exception_becomes_result(robot,monkeypatch):
    import mink
    def broken(*args,**kwargs):
        raise RuntimeError('solver unavailable')
    monkeypatch.setattr(mink,'solve_ik',broken)
    result=robot.move_to('red_part')
    assert not result['ok']
    assert 'solver unavailable' in result['reason']

def test_simulations_are_independent(robot):
    other=Robot(); before=other.data.qpos.copy(); t=other.data.time
    assert robot.move_to('red_part')['ok']
    assert robot.grasp()['ok']
    np.testing.assert_array_equal(other.data.qpos,before)
    assert other.data.time==t
    assert robot.ik_model.nq == 9
    assert robot.model.nq == 23

def test_release_and_lift_alone(robot):
    assert robot.release()['ok']
    start=robot.tcp.copy()
    assert robot.lift(.10)['ok']
    assert np.linalg.norm(robot.tcp-(start+[0,0,.10]))<.02
