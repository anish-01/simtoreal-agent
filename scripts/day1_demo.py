"""Run a deterministic Day 1 plan with optional overhead snapshot."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from actions import Robot

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--image',type=Path)
    args=parser.parse_args()
    robot=Robot()
    results=[]
    for name,values in [('move_to',('red_part',)),('grasp',()),('lift',()),('move_to',('bin_a',)),('release',()),('home',())]:
        start=robot.data.time
        result=getattr(robot,name)(*values)
        results.append({'action':name,**result,'simulated_seconds':round(robot.data.time-start,3)})
        if not result['ok']:
            print(json.dumps(results,indent=2)); return 1
    print(json.dumps(results,indent=2))
    if args.image:
        import mujoco
        from PIL import Image
        args.image.parent.mkdir(parents=True,exist_ok=True)
        with mujoco.Renderer(robot.model,height=960,width=1280) as renderer:
            renderer.update_scene(robot.data,camera='top_cam')
            Image.fromarray(renderer.render()).save(args.image)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
