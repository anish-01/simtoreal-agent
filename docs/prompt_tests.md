# Planner prompt tests

Run 2026-10-14 02:10 with `llama3.2:3b`, temperature 0.2, JSON mode. Prompt: `planner.SYSTEM_PROMPT`. Times include network latency.

**Result: 5/5 valid.**

| # | Task | Result | Seconds |
| --- | --- | --- | --- |
| 1 | Put the red part in bin A | valid | 2.68 |
| 2 | Put the blue part in bin B | valid | 1.74 |
| 3 | Sort both parts by color: red part to bin A, blue part to bin B | valid | 2.90 |
| 4 | Put both parts in bin B | valid | 2.83 |
| 5 | Move the blue part to bin A, then go home | valid | 1.67 |

## Replies

### 1. Put the red part in bin A

```json
{
  "plan_id": 1,
  "steps": [
    {
      "action": "move_to",
      "target": "red_part"
    },
    {
      "action": "grasp"
    },
    {
      "action": "move_to",
      "target": "bin_a"
    },
    {
      "action": "release"
    }
  ]
}
```

### 2. Put the blue part in bin B

```json
{
  "plan_id": 2,
  "steps": [
    {
      "action": "move_to",
      "target": "blue_part"
    },
    {
      "action": "grasp"
    },
    {
      "action": "move_to",
      "target": "bin_b"
    },
    {
      "action": "release"
    }
  ]
}
```

### 3. Sort both parts by color: red part to bin A, blue part to bin B

```json
{
  "plan_id": 3,
  "steps": [
    {
      "action": "move_to",
      "target": "red_part"
    },
    {
      "action": "grasp"
    },
    {
      "action": "move_to",
      "target": "bin_a"
    },
    {
      "action": "release"
    },
    {
      "action": "move_to",
      "target": "blue_part"
    },
    {
      "action": "grasp"
    },
    {
      "action": "move_to",
      "target": "bin_b"
    },
    {
      "action": "release"
    }
  ]
}
```

### 4. Put both parts in bin B

```json
{
  "plan_id": 4,
  "steps": [
    {
      "action": "move_to",
      "target": "red_part"
    },
    {
      "action": "grasp"
    },
    {
      "action": "move_to",
      "target": "bin_b"
    },
    {
      "action": "release"
    },
    {
      "action": "move_to",
      "target": "blue_part"
    },
    {
      "action": "grasp"
    },
    {
      "action": "move_to",
      "target": "bin_b"
    },
    {
      "action": "release"
    }
  ]
}
```

### 5. Move the blue part to bin A, then go home

```json
{
  "plan_id": 5,
  "steps": [
    {
      "action": "move_to",
      "target": "blue_part"
    },
    {
      "action": "grasp"
    },
    {
      "action": "move_to",
      "target": "bin_a"
    },
    {
      "action": "release"
    },
    {
      "action": "home"
    }
  ]
}
```
