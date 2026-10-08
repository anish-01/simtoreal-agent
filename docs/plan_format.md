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
