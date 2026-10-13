"""Planner: turns a plain-English task into candidate JSON robot plans via Llama 3.1 on AMD."""
import json
import math
import os
import re

ACTIONS = ('move_to', 'grasp', 'release', 'lift', 'home')
PARTS = ('red_part', 'blue_part')
TARGETS = PARTS + ('bin_a', 'bin_b')
MIN_LIFT, MAX_LIFT = .05, .30
MAX_STEPS = 16

SYSTEM_PROMPT = f"""You plan pick-and-place tasks for a Franka Panda robot arm on a factory table.

Objects:
- red_part, blue_part: small cubes on the table
- bin_a, bin_b: open bins on the table

Actions (one JSON object per step):
- {{"action": "move_to", "target": <object>}}: hover 10 cm above a part, or 20 cm above a bin
- {{"action": "grasp"}}: pick up the part. Only directly after move_to that part, with an empty gripper
- {{"action": "release"}}: open the gripper and drop the held part
- {{"action": "lift", "height": <metres, {MIN_LIFT} to {MAX_LIFT}>}}: move straight up; height is optional
- {{"action": "home"}}: return the arm to its start pose

To put a part in a bin: move_to the part, grasp, move_to the bin, release.
The gripper holds one part at a time.

Reply with ONLY one JSON object and no other text:
{{"plan_id": 1, "steps": [ ...steps... ]}}"""


def validate(plan):
    """Check a plan against docs/plan_format.md. Returns (ok, reason)."""
    if not isinstance(plan, dict):
        return False, 'plan is not a JSON object'
    steps = plan.get('steps')
    if not isinstance(steps, list) or not steps:
        return False, 'steps must be a non-empty list'
    if len(steps) > MAX_STEPS:
        return False, f'too many steps ({len(steps)} > {MAX_STEPS})'
    hover = held = None
    for n, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            return False, f'step {n} is not an object'
        name = step.get('action')
        if name not in ACTIONS:
            return False, f'step {n}: unknown action {name!r}'
        allowed = {'action', 'target'} if name == 'move_to' else {'action', 'height'} if name == 'lift' else {'action'}
        if set(step) - allowed:
            return False, f'step {n}: unexpected fields {sorted(set(step) - allowed)}'
        if name == 'move_to':
            if step.get('target') not in TARGETS:
                return False, f'step {n}: unknown target {step.get("target")!r}'
            hover = step['target'] if step['target'] in PARTS else None
            continue
        if name == 'grasp':
            if hover is None:
                return False, f'step {n}: grasp must directly follow move_to a part'
            if held is not None:
                return False, f'step {n}: grasp while already holding {held}'
            held = hover
        elif name == 'release':
            held = None
        elif name == 'lift' and 'height' in step:
            h = step['height']
            if isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h) or not MIN_LIFT <= h <= MAX_LIFT:
                return False, f'step {n}: lift height must be {MIN_LIFT}-{MAX_LIFT} m'
        hover = None
    return True, ''


def parse(text):
    """Parse a model reply into a plan dict, tolerating text or a code fence around the JSON."""
    match = re.search(r'\{.*\}', text or '', flags=re.S)
    if not match:
        raise ValueError('no JSON object in reply')
    return json.loads(match.group(0))


def client():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv()
    return OpenAI(base_url=os.environ['LLM_BASE_URL'], api_key=os.getenv('LLM_API_KEY') or 'EMPTY')


def request_plan(task, temperature=.2, plan_id=1, llm=None):
    """Ask the LLM for one plan. Returns (plan or None, reason, raw reply)."""
    llm = llm or client()
    reply = llm.chat.completions.create(
        model=os.getenv('LLM_MODEL') or 'meta-llama/Llama-3.1-8B-Instruct',
        messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': task}],
        temperature=temperature,
        max_tokens=512,
        response_format={'type': 'json_object'},
    )
    raw = reply.choices[0].message.content or ''
    try:
        plan = parse(raw)
    except ValueError as exc:
        return None, f'invalid JSON: {exc}', raw
    ok, reason = validate(plan)
    if not ok:
        return None, reason, raw
    plan['plan_id'] = plan_id
    return plan, '', raw
