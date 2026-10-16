"""Approval boundaries, session resets and the backend-to-page contract."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from exporter import export_approved


@pytest.fixture
def result():
    plan = json.loads((app.ROOT / 'examples/red_to_bin_a.json').read_text())
    row = dict(plan_id=plan['plan_id'], status='OK', score=100, reason='OK',
               result=dict(success=True, time=6.7, steps_done=6, collisions=0, dropped=False, failed_step=None),
               vision=dict(answer='yes', needs_review=False, confidence=.9, reason='Cube inside bin A'))
    return dict(task='Put the red part in bin A', run_id='test-run', goals={'red_part': 'bin_a'},
                plans=[plan], best=row, table=[row], error='',
                timings={'llm_s': 2.5, 'total_s': 9}, amd={'gpu': 'Reported GPU', 'plans_per_s': 3.2})


def test_export_contains_approved_plan_and_readable_steps(result, tmp_path):
    program, steps = export_approved(result, root=tmp_path)
    saved = json.loads(program.read_text())
    assert saved['plan'] == result['plans'][0]
    assert saved['task'] == result['task'] and saved['score'] == 100
    assert saved['vision'] == result['best']['vision']
    assert saved['approved_at'].endswith('+00:00')
    assert '1. Move above red part' in steps.read_text()
    assert '3. Lift 0.15 meters' in steps.read_text()
    assert export_approved(result, root=tmp_path)[0] != program


@pytest.mark.parametrize('failure', ['no-result', 'no-best', 'collision', 'dropped', 'failed-step', 'missing-plan', 'invalid-plan'])
def test_export_refuses_failed_or_missing_plans(result, tmp_path, failure):
    if failure == 'no-result':
        result = None
    elif failure == 'no-best':
        result['best'] = None
    elif failure == 'missing-plan':
        result['plans'] = []
    elif failure == 'invalid-plan':
        result['plans'][0]['steps'] = [{'action': 'unknown'}]
    else:
        key, value = {'collision': ('collisions', 1), 'dropped': ('dropped', True),
                      'failed-step': ('failed_step', 2)}[failure]
        result['best']['result'][key] = value
    with pytest.raises(ValueError):
        export_approved(result, reviewed=True, root=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('vision', [None, {'answer': 'unknown', 'needs_review': True}, {'answer': 'no', 'needs_review': True}])
def test_uncertain_vision_requires_explicit_review(result, tmp_path, vision):
    result['best']['vision'] = vision
    with pytest.raises(ValueError, match='acknowledgement'):
        export_approved(result, root=tmp_path)
    program, _ = export_approved(result, reviewed=True, root=tmp_path)
    assert json.loads(program.read_text())['human_reviewed'] is True


def test_page_displays_backend_metrics_and_escapes_model_text(result):
    result['table'][0]['reason'] = '<script>alert(1)</script>'
    rendered = app.presentation(result)
    assert rendered[7]['interactive'] is True
    assert 'best' in rendered[2] and '&lt;script&gt;' in rendered[2]
    assert '<script>' not in rendered[2]
    assert 'Reported GPU' in rendered[6] and '3.2' in rendered[6]
    assert 'MI300X' not in rendered[6]
    result['best'] = None
    result['error'] = 'no safe plan found'
    assert app.presentation(result)[7]['interactive'] is False


def test_media_cannot_escape_run_folder(tmp_path):
    secret = tmp_path / 'secret.png'
    secret.write_text('private')
    assert app.media_path(str(secret)) is None
    assert app.media_path(str(app.ROOT / 'runs/missing.png')) is None


def test_new_run_clears_previous_approval_and_handles_server_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionError('private endpoint details')
    monkeypatch.setattr(app.pipeline, 'run_task', fail)
    initial, final = list(app.run_task('Put red in bin A', 'Factory'))
    assert initial[0] is None and initial[7]['interactive'] is False and initial[9] is None
    assert initial[11]['interactive'] is False
    assert final[0] is None and final[7]['interactive'] is False and final[11]['interactive'] is True
    assert 'model servers' in final[1] and 'private endpoint details' not in final[1]


def test_empty_task_does_not_call_backend(monkeypatch):
    monkeypatch.setattr(app.pipeline, 'run_task', lambda *a, **kw: pytest.fail('backend called'))
    assert 'Enter a task' in list(app.run_task('  ', 'Factory'))[-1][1]


def test_run_uses_selected_scene_and_preserves_session_result(result, monkeypatch):
    calls = []
    def run(task, **kwargs):
        calls.append((task, kwargs['scene']))
        return copy.deepcopy(result)
    monkeypatch.setattr(app.pipeline, 'run_task', run)
    final = list(app.run_task(' task ', 'Blue part out of reach'))[-1]
    assert calls == [('task', app.DEMO_TASKS['unreachable']['scene'])]
    assert final[0] == result and final[7]['interactive'] is True


def test_gradio_page_builds_with_private_session_callbacks():
    page = app.build_app()
    config = page.get_config_file()
    assert all(dep['api_visibility'] == 'private' for dep in config['dependencies'])
    assert any(component['type'] == 'state' for component in config['components'])
