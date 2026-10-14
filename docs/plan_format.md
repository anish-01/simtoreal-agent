# Plan format

The planner returns each plan as JSON in this format:

```json
{"plan_id": 1, "steps": [
  {"action": "move_to", "target": "red_part"},
  {"action": "grasp"},
  {"action": "move_to", "target": "bin_a"},
  {"action": "release"}
]}
```

## Objects

- `red_part`
- `blue_part`
- `bin_a`
- `bin_b`

## Actions

- `move_to` (takes a `target` object)
- `grasp`
- `release`
- `lift`
- `home`

## Action behavior

- `move_to` a part hovers 10 cm above its center; a bin target hovers 20 cm above its floor origin.
- `grasp` requires the preceding move to hover over a part. It descends, closes and lifts back to the hover position, verifying physical grasp and lift.
- `release` opens the gripper and clears the held-part state.
- `lift` moves straight up 15 cm by default, or a positive height in meters.
- `home` returns the arm to its saved starting joint pose, preserving gripper command.

Instantiate one `actions.Robot` per candidate plan. All public actions return `{"ok": true, "reason": ""}` or `{"ok": false, "reason": "..."}`. Stop the candidate on failure. Each action has one four-second simulated-time budget; it may leave a partially moved scene on failure.

## Simulator handoff

Call `simulator.run_plan(plan, goals, run_dir)` with a separate task goal mapping,
e.g. `{"red_part": "bin_a", "blue_part": "bin_b"}`. The simulator must not derive
the intended goal from a candidate's steps. Results and media are described in
[the Day 2 API](day2_simulator.md).
