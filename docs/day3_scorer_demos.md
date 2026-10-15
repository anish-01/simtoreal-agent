# Day 3: scorer and three demo tasks

Implements Shailesh's [#24](https://github.com/anish-01/simtoreal-agent/issues/24)
and [#25](https://github.com/anish-01/simtoreal-agent/issues/25), October 14, 2026.

## Scorer API

`scorer.score(results)` accepts the simulator result dictionaries and returns
rows containing `plan_id`, `score`, `status`, `reason`, and the original `result`.
The backend calls this scorer directly and selects only an `OK` row as `best`.

Reject first with score zero: arm-table contact, a dropped part, a failed step,
an unmet placement goal, or a simulation/setup/worker failure. Reasons identify
the problem in plain language. A claimed success with nonpositive or nonfinite
time/step measurements also fails closed.

For safe candidates only:

`score = 60 + 20 × fastest_safe_time / time + 20 × shortest_safe_steps / steps_done`

The step count is a simplicity proxy for smoothness; it does not measure joint
jerk. Time includes the simulator's final settling interval. Rejected candidates
never affect the reference minima. Scores round to two decimals, OK rows sort
highest first, rejected rows come last, and ties preserve candidate order.
Reasons explain extra seconds and steps; a plan only reaches 100 if it is both
fastest and shortest. Input result dictionaries are preserved.

## UI example definitions

Import `DEMO_TASKS` from `demo_tasks.py` for the task labels, independent goal
mappings, scene paths and saved reference plans. The rejection example requires
its own scene; sending the same text to the ordinary scene would be reachable.
Pass the selected scene to `pipeline.run_task(..., scene=demo['scene'])`.

| Example | Task | Expected result |
| --- | --- | --- |
| Easy | Put the red part in bin A | Several OK plans; select the highest score |
| Medium | Sort both parts by color | At least one OK plan; red fully inside A and blue fully inside B |
| Should reject | Put the blue part in bin B | Every saved candidate fails with “could not reach”; `best` is null and error is “no safe plan found” |

`scenes/factory_unreachable.xml` copies the factory scene and places blue at
(1.05, 0.12, 0.025) m. Its table extends to x=1.25 m so the cube remains supported
instead of falling. Names, robot and `top_cam` match the normal scene.

## Reproduce

Use the Python environment with `requirements-sim.txt`, `requirements-ai.txt`
and pytest installed, as in the README:

```sh
python -m pytest -q
SIM_WORKERS=4 python scripts/demo_tasks.py
```

The default command sends eight copies of each reference plan through the real
backend and process-based physics/video runner, then checks the expected outcome.
It explicitly reports **offline saved plans**: its fixture client returns known
goals/plans and performs no model inference. This validates the scorer, combined
two-part placement, scene rejection, media output and no-safe-plan behavior.
Each run saves the normal pipeline JSON and per-candidate MP4/PNG under ignored
`runs/`. Exit code 1 means an expected outcome failed.

Validated locally on macOS / Python 3.12: **94 tests passed**. The full eight-plan
offline run accepted **8/8 easy** and **8/8 medium** candidates, and rejected
**8/8 unreachable** candidates at step 1 with “could not reach target”. The
unreachable response selected no best plan and reported “no safe plan found”.

For full typed-task validation with the team's AMD endpoint configured:

```sh
SIM_WORKERS=4 python scripts/demo_tasks.py --live
```

Live mode uses goal extraction and eight generated candidates from the configured
planner. It verifies the extracted goals against the example's independent
expected mapping. Live AMD inference remains unverified here because the endpoint
is not configured. No AMD latency or model-diversity claims come from offline runs.
`--demo easy|medium|unreachable`, `-n 1..8`, and `--sequential` support individual
checks. macOS rendering requires graphics access; Linux requires the rendering
libraries described in the Day 2 documentation.
