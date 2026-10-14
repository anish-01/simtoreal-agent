"""Planner: turns a plain-English task into candidate JSON robot plans via Llama 3.1 on AMD."""
import json
import logging
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor

ACTIONS = ('move_to', 'grasp', 'release', 'lift', 'home')
PARTS = ('red_part', 'blue_part')
BINS = ('bin_a', 'bin_b')
TARGETS = PARTS + BINS
MIN_LIFT, MAX_LIFT = .05, .30
MAX_STEPS = 16
RETRIES = 2
# One style per candidate, so the 8 plans really differ.
STYLES = (
    'use the fewest steps possible',
    'lift the part 0.25 m right after grasping, before moving it',
    'lift the part only 0.05 m right after grasping, before moving it',
    'return the arm home at the end',
    'start by moving the arm home',
    'lift the part 0.15 m after grasping and return home at the end',
    'lift 0.1 m after every release',
    'lift 0.3 m after grasping, then return home at the end',
)


log = logging.getLogger(__name__)

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


def temperatures(n, low=.2, high=1.):
    """n temperatures spread evenly from low to high."""
    return [low] if n == 1 else [round(low + (high - low) * i / (n - 1), 3) for i in range(n)]


def _one_plan(task, temperature, plan_id, n, llm):
    """One candidate: first attempt plus up to RETRIES retries. Returns (plan or None, reasons)."""
    reasons = []
    for _ in range(1 + RETRIES):
        try:
            style = STYLES[(plan_id - 1) % len(STYLES)]
            plan, reason, _ = request_plan(f'{task}\n\n(Candidate plan {plan_id} of {n}. Style: {style}.)', temperature, plan_id, llm)

        except Exception as exc:
            plan, reason = None, f'request failed: {exc}'
        if plan:
            return plan, reasons
        reasons.append(reason)
    return None, reasons


def generate_plans(task, n=8, llm=None):
    """Ask for n plans in parallel, temperatures 0.2 to 1.0. Invalid plans are retried, then dropped."""
    llm = llm or client()
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(lambda i: _one_plan(task, temperatures(n)[i], i + 1, n, llm), range(n)))
    plans = [plan for plan, _ in results if plan]
    for i, (plan, reasons) in enumerate(results, 1):
        if plan is None:
            log.warning('plan %d dropped after %d attempts: %s', i, len(reasons), '; '.join(reasons))
    return plans


GOALS_PROMPT = """A robot operator gives a task for a robot cell with parts red_part, blue_part and bins bin_a, bin_b.
Say which part must end up in which bin when the task is done.
Reply with ONLY one JSON object: {"goals": {"<part>": "<bin>", ...}}
Include only the parts the task asks to move. If the task asks for nothing possible, reply {"goals": {}}."""


def extract_goals(task, llm=None):
    """Ask the LLM what the finished task looks like, e.g. {'red_part': 'bin_a'}. Returns (goals or None, reason).

    The simulator checks plans against these goals, so they come from the task, never from a candidate plan.
    """
    llm = llm or client()
    try:
        reply = llm.chat.completions.create(
            model=os.getenv('LLM_MODEL') or 'meta-llama/Llama-3.1-8B-Instruct',
            messages=[{'role': 'system', 'content': GOALS_PROMPT}, {'role': 'user', 'content': task}],
            temperature=0, max_tokens=128, response_format={'type': 'json_object'})
        goals = parse(reply.choices[0].message.content).get('goals')
    except Exception as exc:
        return None, f'could not read the task goals: {exc}'
    if not isinstance(goals, dict) or not goals:
        return None, 'the task does not ask to put a part in a bin'
    if any(part not in PARTS or bin_name not in BINS for part, bin_name in goals.items()):
        return None, f'unknown part or bin in goals: {goals}'
    return goals, ''
