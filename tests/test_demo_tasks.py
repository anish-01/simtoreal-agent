import importlib.util
from pathlib import Path
import pytest
from actions import Robot
from demo_tasks import DEMO_TASKS, expected_outcome
from pipeline import run_task

spec = importlib.util.spec_from_file_location('demo_cli', Path(__file__).resolve().parents[1] / 'scripts/demo_tasks.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_unreachable_cube_stays_supported_on_table():
    robot = Robot(scene=DEMO_TASKS['unreachable']['scene'])
    assert robot.data.body('blue_part').xpos[0] > 1.
    assert .02 < robot.data.body('blue_part').xpos[2] < .03
    assert robot.move_to('blue_part') == {'ok': False, 'reason': 'could not reach target'}


@pytest.mark.parametrize('name', list(DEMO_TASKS))
def test_demo_pipeline_expected_outcomes(tmp_path, name):
    demo = DEMO_TASKS[name]
    result = run_task(demo['task'], n=2, llm=cli.SavedPlanClient(demo),
                      scene=demo['scene'], root=tmp_path, parallel=True)
    assert expected_outcome(name, result), result
    assert len(result['table']) == 2
    assert all(Path(row['result']['video_path']).exists() for row in result['table'])
