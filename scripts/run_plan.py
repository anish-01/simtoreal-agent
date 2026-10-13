"""P12: typed task (or saved plan JSON) -> plan -> Panda actions in MuJoCo."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner
from actions import Robot, PARTS


def where(robot, part):
    """Name of the bin the part rests in, or 'table'."""
    p = robot.data.body(part).xpos
    for bin_name in ('bin_a', 'bin_b'):
        b = robot.data.body(bin_name).xpos
        if abs(p[0] - b[0]) < .08 and abs(p[1] - b[1]) < .08 and p[2] < .09:
            return bin_name
    return 'table'


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--task', help='plain-English task sent to the planner LLM')
    source.add_argument('--plan', type=Path, help='saved plan JSON file')
    parser.add_argument('--save', type=Path, help='save the plan JSON here')
    parser.add_argument('--image', type=Path, help='save a top_cam snapshot here')
    args = parser.parse_args()

    if args.task:
        plan, reason, raw = planner.request_plan(args.task)
        if plan is None:
            print(f'Planner failed: {reason}\n{raw}')
            return 1
    else:
        plan = json.loads(args.plan.read_text())
        ok, reason = planner.validate(plan)
        if not ok:
            print(f'Invalid plan: {reason}')
            return 1
    print('Plan:', json.dumps(plan))
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(plan, indent=2))

    robot = Robot()
    code = 0
    for n, step in enumerate(plan['steps'], 1):
        name = step['action']
        values = (step['target'],) if name == 'move_to' else (step['height'],) if 'height' in step else ()
        start = robot.data.time
        result = getattr(robot, name)(*values)
        print(f'{n}. {name} {values[0] if values else ""}: {"ok" if result["ok"] else "FAILED " + result["reason"]} '
              f'({robot.data.time - start:.2f} s sim)')
        if not result['ok']:
            code = 1
            break
    for part in PARTS:
        print(f'{part} ended in: {where(robot, part)}')

    if args.image:
        import mujoco
        from PIL import Image
        args.image.parent.mkdir(parents=True, exist_ok=True)
        with mujoco.Renderer(robot.model, height=960, width=1280) as renderer:
            renderer.update_scene(robot.data, camera='top_cam')
            Image.fromarray(renderer.render()).save(args.image)
        print('Snapshot:', args.image)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
