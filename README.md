# SimToReal Agent

**Test before you touch.** SimToReal Agent is a hackathon project for testing AI-generated robot plans in simulation before an operator approves an export.

The planned workflow is: an operator describes a task → Llama 3.1 8B on AMD MI300X proposes eight JSON plans → independent MuJoCo simulations test the plans with a Franka Panda arm → a scorer rejects unsafe candidates → Pixtral checks the final camera image → the operator reviews the best plan and approves an export.

Built for the AMD Developer Hackathon: ACT III, Track 1 (Intelligent Industry).

## Current status

The Day 1 simulation action layer is implemented for [issue #16](https://github.com/anish-01/simtoreal-agent/issues/16):

- A factory scene with a Panda arm, table, red and blue parts, two open bins, and a fixed overhead camera named `top_cam`.
- Five actions: `move_to`, `grasp`, `release`, `lift`, and `home`.
- Independent simulation state for each `Robot` instance, with arm-only mink inverse kinematics.
- Structured success and failure results, target validation, physical grasp checks, and a four-second simulated-time limit per action.
- A deterministic pick-and-place demo and 24 passing tests, including both colors placed in their corresponding bins.

The planner client, process-based simulation runner, scorer, video recording,
Pixtral verifier, operator UI, and approval exports are implemented. Live AMD
model services need endpoint configuration and validation. The saved-plan demo
runs without an AMD endpoint and does not connect to a real robot.

## Operator page (Days 4–5)

Use Python 3.12 and install the UI plus backend dependencies:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-ui.txt
cp .env.example .env
# Set LLM_BASE_URL and VLM_BASE_URL to the team's configured model endpoints.
.venv/bin/python app.py
```

Open http://127.0.0.1:7860. Choose one of the three examples or type a task,
then select **Test 8 plans in simulation**. The out-of-reach example also selects
the extended scene; the other examples restore the normal factory scene.
The page shows progress, colored results with the best row highlighted, the
best-plan video, all available candidate images, and the camera check.

Review the video and image before **Approve and export this plan**. Unknown or
disagreeing camera checks require an explicit human-review acknowledgement.
Approval saves JSON and readable steps under `exports/<unique-id>/` and offers
both as downloads. Each export records the task, plan, goals, score, UTC approval
time, vision check, and simulation evidence. Rejected plans cannot be exported.
Editing the task or scene, choosing an example, or starting a run clears the
previous approval and download links. Results belong to each browser session.

The AMD panel uses the backend's `amd` and `timings` fields from the current run;
it does not invent performance numbers. GPU identity is supplied by `GPU_NAME`
in the deployment configuration. Missing values say “Not reported”. This page
exports files only; it never connects to or commands a real robot.

The default server listens locally. For the team's deployment, set
`GRADIO_SERVER_NAME` and optionally `GRADIO_SERVER_PORT`. Share only the app
port; keep model endpoints private. See [UI validation and handoff](docs/day4_day5_ui.md).

## Quick start

Use Python 3.12. From the repository root on macOS or Linux:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-sim.txt
.venv/bin/python scripts/day1_demo.py
```

The demo picks up the red part, lifts it, moves it to bin A, releases it, and returns the arm home. It prints an action result and simulated duration for each step, stopping with a nonzero exit code if an action fails.

To save a 1280 × 960 overhead snapshot after the run:

```sh
.venv/bin/python scripts/day1_demo.py --image runs/day1_final.png
```

Rendering needs an available graphics context. On macOS, allow graphics access if prompted. Physics tests and the demo without `--image` do not create a renderer. Generated files in `runs/` are ignored by Git.

## Using the robot actions

Create one `Robot` for each candidate plan and execute its actions sequentially:

```python
from actions import Robot

robot = Robot()
steps = [
    ("move_to", ("red_part",)),
    ("grasp", ()),
    ("lift", (0.15,)),
    ("move_to", ("bin_a",)),
    ("release", ()),
    ("home", ()),
]

for name, args in steps:
    result = getattr(robot, name)(*args)
    if not result["ok"]:
        print(f"Plan rejected: {result['reason']}")
        break
```

Successful actions return `{"ok": true, "reason": ""}`; failed actions return `{"ok": false, "reason": "..."}`. Stop and discard a failed candidate: failure can leave its scene partially moved. Use a separate instance for every parallel candidate; one instance is not intended for concurrent callers.

| Action | Behavior |
| --- | --- |
| `move_to(target)` | Hovers 10 cm above a part or 20 cm above a bin's floor origin. Rejects unknown or unreachable targets. |
| `grasp()` | Requires hovering over a part. Descends, closes, and lifts; checks both finger contacts and actual part lift. |
| `release()` | Opens the gripper and clears the held-part state. |
| `lift(height=0.15)` | Moves vertically upward by a positive height in meters. |
| `home()` | Returns to the starting arm joint pose while preserving the gripper command. |

Allowed targets are `red_part`, `blue_part`, `bin_a`, and `bin_b`. See the [plan format](docs/plan_format.md) for the planner JSON contract.

## Validation

```sh
.venv/bin/python -m pip install pytest==9.1.1
.venv/bin/python -m pytest -q
```

The Day 1 validation passed all 24 tests on macOS Apple Silicon with Python 3.12.13. Tests cover physical red and blue pick-and-place, invalid and unreachable targets, grasp preconditions, invalid lifts, timeout behavior for all five actions, solver exceptions, and isolation between simulation instances.

The reference red demo took 6.726 simulated seconds across six actions. This is simulation duration, not a wall-clock or AMD performance benchmark.

## Day 2: simulate a plan and record video

```sh
.venv/bin/python scripts/simulate_plan.py --plan examples/red_to_bin_a.json \
  --goals '{"red_part":"bin_a"}'
```

Each candidate saves a 30 fps MP4, a large final image and result JSON under
`runs/`. Results include task success, completed steps, simulated time,
arm-table collision episodes, dropped-part status and failure reason.
Use `run_plan(plan, goals, run_dir)` in the backend; pass the task's goal
independently of the candidate plan. See [Day 2 API and handoff](docs/day2_simulator.md).

To connect a typed task to Anish's configured AMD planner:

```sh
.venv/bin/python scripts/simulate_plan.py --task 'put the red part in bin A' \
  --goals '{"red_part":"bin_a"}'
```

Day 2 validation: 63 tests passed, including physical placements, wrong-bin and
outside-bin rejection, geometry-based bounds, failure stopping and decoded video.
The saved-plan demo is verified locally; the live AMD milestone needs the team's
endpoint configuration and joint video review.

## Day 3: rank plans and verify three demos

The backend now rejects unsafe results first, then ranks safe plans out of 100:
60 for success, up to 20 for speed, and up to 20 for fewer steps. Every row has
a plain reason, and rejected plans can never be selected as the best.

```sh
SIM_WORKERS=4 .venv/bin/python scripts/demo_tasks.py
```

This checks eight saved candidates each for red-to-A, sorting both parts, and
an out-of-reach blue part. It runs real physics and records videos without model
inference. Add `--live` to validate the same tasks against the configured AMD
planner. See [Day 3 scorer, demo definitions and validation](docs/day3_scorer_demos.md)
for the API, expected results, and UI handoff.

## Limitations

- The controller is tuned to the included scene and Panda model. A successful action does not certify a collision-free path; the simulator measures arm-table collisions and dropped parts; broader collision checks remain future work.
- The four-second limit bounds simulated physics time. A separate wall-clock worker timeout is needed to interrupt a stalled native solver.
- The arm can occlude the blue part from the overhead camera when at home.
- Missing or incompatible scene files raise setup errors when constructing a `Robot`.

## Project files

| Path | Purpose |
| --- | --- |
| `actions.py` | Bounded Panda action controller. |
| `scenes/factory.xml` | Factory scene used by the controller. |
| `scenes/panda/` | Vendored official Panda model, assets, license, and local modification notes. |
| `scripts/day1_demo.py` | Local pick-and-place demo with an optional camera snapshot. |
| `tests/test_actions.py` | Physics and failure-handling tests. |
| `requirements-sim.txt` | Pinned simulation dependencies. |
| `simulator.py`, `scripts/simulate_plan.py` | Goal-based execution, safety measurements, images and video. |
| `planner.py`, `runlog.py` | AMD planner requests, candidate generation and run logging. |
| `pipeline.py`, `scorer.py` | Parallel task execution and safety-first weighted ranking. |
| `demo_tasks.py`, `scripts/demo_tasks.py` | Three shared UI examples and offline/live validation. |
| `app.py` | Gradio operator page, session results, media review and AMD metrics. |
| `exporter.py` | Explicit approval, safety checks and downloadable JSON/readable steps. |
| `verifier.py` | Pixtral final-image checks and human-review flags. |

The Panda model comes from MuJoCo Menagerie and retains its Apache 2.0 license. See [model provenance and modifications](scenes/panda/LOCAL_CHANGES.md).

## Implementation documentation

- [Day 1 implementation notes](docs/day1_actions.md): changes, necessity, validation, alternatives, and remaining limits.
- [Explanation document](docs/day1_actions_explanation.docx): the same rationale in a three-page Word document.
- [Draft PR description](docs/day1_pr_draft.md).

## Team and task board

**Visionary Creators**

- Anish Jaiswal ([@anish-01](https://github.com/anish-01)): AI, AMD, backend.
- Shailesh ([@shaileshkryadav](https://github.com/shaileshkryadav)): robot simulation, UI.

Track daily work on the [SimToReal Build project board](https://github.com/users/anish-01/projects/3), [issues](https://github.com/anish-01/simtoreal-agent/issues), and [milestones](https://github.com/anish-01/simtoreal-agent/milestones).
