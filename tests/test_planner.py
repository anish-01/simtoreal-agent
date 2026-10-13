"""Offline tests for the planner prompt contract: no LLM server needed."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner

RED_TO_A = {'plan_id': 1, 'steps': [
    {'action': 'move_to', 'target': 'red_part'}, {'action': 'grasp'},
    {'action': 'move_to', 'target': 'bin_a'}, {'action': 'release'}]}


def test_plan_format_example_is_valid():
    assert planner.validate(RED_TO_A) == (True, '')


def test_sort_both_with_lift_and_home_is_valid():
    plan = {'steps': [
        {'action': 'move_to', 'target': 'red_part'}, {'action': 'grasp'}, {'action': 'lift', 'height': .1},
        {'action': 'move_to', 'target': 'bin_a'}, {'action': 'release'},
        {'action': 'move_to', 'target': 'blue_part'}, {'action': 'grasp'}, {'action': 'lift'},
        {'action': 'move_to', 'target': 'bin_b'}, {'action': 'release'}, {'action': 'home'}]}
    assert planner.validate(plan)[0]


@pytest.mark.parametrize('plan, reason', [
    ([], 'not a JSON object'),
    ({'steps': []}, 'non-empty'),
    ({'steps': [{'action': 'fly'}]}, 'unknown action'),
    ({'steps': [{'action': 'move_to', 'target': 'bin_c'}]}, 'unknown target'),
    ({'steps': [{'action': 'move_to'}]}, 'unknown target'),
    ({'steps': [{'action': 'grasp'}]}, 'directly follow'),
    ({'steps': [{'action': 'move_to', 'target': 'bin_a'}, {'action': 'grasp'}]}, 'directly follow'),
    ({'steps': [{'action': 'move_to', 'target': 'red_part'}, {'action': 'lift'}, {'action': 'grasp'}]}, 'directly follow'),
    ({'steps': [{'action': 'move_to', 'target': 'red_part'}, {'action': 'grasp'},
                {'action': 'move_to', 'target': 'blue_part'}, {'action': 'grasp'}]}, 'already holding'),
    ({'steps': [{'action': 'lift', 'height': 2}]}, 'lift height'),
    ({'steps': [{'action': 'lift', 'height': True}]}, 'lift height'),
    ({'steps': [{'action': 'grasp', 'target': 'red_part'}]}, 'unexpected fields'),
    ({'steps': [{'action': 'home'}] * 17}, 'too many steps'),
])
def test_invalid_plans_are_rejected(plan, reason):
    ok, why = planner.validate(plan)
    assert not ok and reason in why


def test_parse_tolerates_think_block_and_fence():
    raw = '<think>hmm</think>\n```json\n' + json.dumps(RED_TO_A) + '\n```'
    assert planner.parse(raw) == RED_TO_A


def test_prompt_names_every_action_and_object():
    for word in planner.ACTIONS + planner.TARGETS:
        assert word in planner.SYSTEM_PROMPT


class FakeLLM:
    def __init__(self, reply):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.reply = reply

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


def test_request_plan_turns_thinking_off_and_sets_plan_id():
    llm = FakeLLM(json.dumps({**RED_TO_A, 'plan_id': 99}))
    plan, reason, _ = planner.request_plan('put red part in bin A', plan_id=3, llm=llm)
    assert reason == '' and plan['plan_id'] == 3
    call = llm.calls[0]
    assert call['extra_body'] == {'chat_template_kwargs': {'enable_thinking': False}}
    assert call['response_format'] == {'type': 'json_object'}


def test_request_plan_reports_bad_json():
    plan, reason, raw = planner.request_plan('x', llm=FakeLLM('sorry, I cannot'))
    assert plan is None and 'invalid JSON' in reason and raw == 'sorry, I cannot'
