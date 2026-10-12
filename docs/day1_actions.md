# Day 1 robot actions implementation

Prepared for Shailesh on October 12, 2026. Implements [D1.4, issue 16](https://github.com/anish-01/simtoreal-agent/issues/16), assigned to `shaileshkryadav`. The other Day 1 issues are assigned to Anish: #13 GPU startup, #14 model serving, and #15 planner endpoint configuration. This change provides the simulation action layer; it does not supply those model services.

## What changed and why

| Change | Necessity |
| --- | --- |
| `actions.py` with a `Robot` instance | Gives each candidate plan independent model, physics data, IK configuration, gripper state and action deadline. |
| `move_to`, `grasp`, `release`, `lift`, `home` | Provides the exact five actions expected by the agreed planner vocabulary. Every call returns `ok` and `reason`. |
| Arm-only mink IK | Prevents the solver from including free cube joints. Only seven arm joint commands are transferred to the physical scene. |
| Gradually interpolated downward TCP targets | Avoids a single abrupt Cartesian target jump. Uses physical actuators rather than teleporting the robot or attaching cubes artificially. |
| Shared four-second simulated-time deadline | A grasp's descent, closing and ascent share one budget. Failure stops further physics stepping; the caller should reject that candidate. |
| Reach and grasp checks | Rejects unknown names, non-finite or excessive lifts, unreachable goals, invalid grasp sequences and solver errors. A grasp needs both finger contacts, nonzero finger opening and actual upward cube motion. |
| Factory scene and licensed Panda assets | The checkout lacked P8-P10 prerequisites. An executable scene was necessary to implement and physically test #16. Includes both parts, open bins, table and fixed `top_cam`. |
| Tests and demo script | Establishes repeatable acceptance evidence and an integration example without requiring the AMD planner. |
| Pinned simulation requirements | Records the dependency versions used for the successful validation. |

The Panda model was copied from official MuJoCo Menagerie revision `0059d4335f8156206f63a35662313385f7ad6d74`. Its Apache 2.0 license is retained. Local changes remove its scene-sized home keyframe, add a TCP site at the fingertip center, and make mesh paths usable both standalone and through the factory include. The original joint values are preserved in `HOME`. The gripper uses the model's 0-255 control range: zero closes, 255 opens. Bins were separated from the parts after the physics test exposed hand contact with a bin wall during descent.

## Integration and validation

Create a fresh `Robot()` per plan. Call an action and inspect its result before executing the next step. On `ok=False`, stop that plan and keep `reason` for the simulator and scorer. Reuse the instance only within that plan. One instance is not intended for concurrent callers.

```python
from actions import Robot
robot = Robot()
for name, args in [('move_to', ('red_part',)), ('grasp', ()),
                   ('move_to', ('bin_a',)), ('release', ())]:
    result = getattr(robot, name)(*args)
    if not result['ok']:
        break
```

Validation on macOS Apple Silicon, Python 3.12.13: **24 tests passed**. Actual MuJoCo tests lift both red and blue cubes with finger contact, deposit each in its corresponding bin, check home joint convergence, and check all action durations. Other tests cover unknown targets, a named part at x=5 m, invalid heights, grasp preconditions, empty grasp, IK exceptions and independent simulations. All five actions also return `timeout` with a deliberately shortened deadline.

The red demo used 1.320 seconds for move-to-part, 1.640 for grasp, 0.690 for lift, 1.040 for move-to-bin, 0.400 for release, and 1.636 for home: **6.726 simulated seconds total**. These are simulation durations, not wall-clock or AMD performance benchmarks. A 1280 by 960 overhead image was rendered and inspected; it confirms the red cube in bin A. The home arm can occlude the blue cube from the overhead view.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-sim.txt pytest==9.1.1
.venv/bin/python -m pytest -q
.venv/bin/python scripts/day1_demo.py --image runs/day1_final.png
```

## Better approaches and remaining limits

For the fixed Day 1 scene, the current controller is small and directly satisfies the action contract. Its numerical parameters are tuned to this Panda model and these cubes. The 0.85 m bound is a conservative precheck, not a complete reachability proof; actual TCP convergence supplies the final check. Cartesian success checks position within 2 cm, while IK requests a downward orientation. Constructor and invalid model errors intentionally raise setup exceptions rather than producing action results.

The next useful improvement is velocity and collision constraints in mink, with table and bin geometry represented in an IK scene whose free object joints are excluded or frozen. Mink documents both limit types. This would control joint speed and discourage collisions during motion. Today, physics contacts are active, but successful actions do not certify collision-free motion, and a carried part may still slip during a later move. The future simulator/scorer should record collisions and dropped parts.

For a changing factory cell, a global planner such as MoveIt with OMPL is a stronger architectural option. MoveIt checks collisions, including attached objects, in motion-plan requests. Adopting it adds ROS setup and model integration, so it is a later investment rather than a prerequisite for this small hackathon action layer. Smooth acceleration-limited trajectories, calibrated gripper friction, release-settling checks and randomized scene tests would also strengthen reliability.

The timeout measures simulated physics time. It cannot interrupt a solver call stalled in native code; the parallel simulator should additionally enforce a wall-clock worker timeout. On action failure, the scene can remain partially moved. Stop and discard that candidate rather than continuing from a presumed clean state. No real robot, AMD endpoint, planner, scorer, video recorder or approval UI is implemented by this change.

## Sources

- Issue and acceptance criteria: https://github.com/anish-01/simtoreal-agent/issues/16
- Official Panda model: https://github.com/google-deepmind/mujoco_menagerie/tree/0059d4335f8156206f63a35662313385f7ad6d74/franka_emika_panda
- MuJoCo Python API: https://mujoco.readthedocs.io/en/latest/python.html
- Mink limits: https://kevinzakka.github.io/mink/api/limits.html
- MoveIt motion planning: https://moveit.picknik.ai/main/doc/concepts/motion_planning.html
