# Day 2 simulator and success check

Implements Shailesh's [#19](https://github.com/anish-01/simtoreal-agent/issues/19)
and [#20](https://github.com/anish-01/simtoreal-agent/issues/20).

```python
from simulator import run_plan
result = run_plan(plan, goals={"red_part": "bin_a"}, run_dir=run_dir)
```

`goals` comes from the task, independently of the candidate plan. Never infer it
from the candidate's release target: that would accept a wrong-bin plan. For a
sorting task pass both parts, for example
`{"red_part": "bin_a", "blue_part": "bin_b"}`. Missing or invalid goals fail
before simulation. The planner's existing plan JSON remains unchanged.

Every call creates its own Robot, renderer, encoder and UUID candidate directory
inside the supplied run folder. This supports later process-based parallel runs
without shared simulation state or output filenames. The existing planner and
runlog APIs are unchanged.

The returned JSON-safe dictionary contains:

| Field | Meaning |
| --- | --- |
| plan_id | Candidate identifier |
| success | All actions and requested placements passed, no arm-table contact or drop |
| steps_done | Number of completed successful actions |
| time | Elapsed simulated seconds, including final one-second settling; excludes Robot initialization |
| collisions | New arm-table contact episodes per arm geom; base-table contact excluded |
| dropped | A grasped part exceeded 6 cm from tcp before an intentional release |
| failed_step | One-based failed action index, or null |
| reason | Action failure, setup/recording error, unsafe result or unmet goal |
| image_path | Absolute path to the 1280×960 final top_cam PNG, or null on recording failure |
| video_path | Absolute path to the finalized H.264 MP4, or null on recording failure |

`result.json` is written beside each candidate's artifacts. Invalid plans/goals
return a failure without creating artifacts. The executor stops dispatching at
the first failed action, then settles and records the failure scene. Robot's
physics-step callback records during motion, including grasp/lift, rather than
only taking a picture after each action. Video defaults to 640×480 at 30 fps of
simulation time and is streamed to ffmpeg instead of retaining frames in RAM.

The success check derives inner faces, floor height and wall-top height from the
bin's box geoms in bin-local coordinates. It transforms all eight cube corners
into that frame, so a cube crossing a wall, balanced on top, below the floor or
still held fails. It permits 1 mm lateral / 2 mm floor tolerance for physics
penetration. Factory bins must retain one floor and four locally axis-aligned
box walls; unsupported bin layouts return a clear setup failure.

## Reproduce

Install `requirements-sim.txt` and `requirements-ai.txt`, then:

```sh
python scripts/simulate_plan.py --plan examples/red_to_bin_a.json \
  --goals '{"red_part":"bin_a"}'
python -m pytest -q
```

Measured on macOS Apple Silicon / Python 3.12.13: **63 tests passed**. The default
30 fps red demo completed all six steps in **7.726 simulated seconds**, with
success=true, collisions=0 and dropped=false. Its final PNG was visually checked;
the tests decode MP4 frames and verify frame count against simulated duration.
This is not an AMD performance measurement.

## Shared milestone #21 handoff

With Anish's AMD model endpoint configured via `.env`, run:

```sh
python scripts/simulate_plan.py --task 'put the red part in bin A' \
  --goals '{"red_part":"bin_a"}'
```

The command saves task.txt, plans.json, goals.json, results.json and candidate
video/image artifacts in one run folder. The saved-plan path is tested locally.
The live AMD request and joint video review remain unverified: no LLM_BASE_URL or
.env exists in this workspace. Keep #21 open until the team runs and watches it.

On headless Linux install system OSMesa libraries and set `MUJOCO_GL=osmesa`
before starting Python (or explicitly choose EGL when available). simulator.py
sets OSMesa by default on Linux before importing MuJoCo. Other entry points that
import MuJoCo first must set the environment themselves. macOS requires access
to its graphics service; sandboxed rendering may be denied.

The action timeouts bound simulation time, not a stuck native IK solver. A later
parallel worker needs a wall-clock watchdog. Collision measurements cover the
assigned arm-table contacts only; they are not a general robot safety certificate.
