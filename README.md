# SimToReal Agent

**Test before you touch.** A factory operator types a robot task in plain English (e.g. "put the red part in bin A"). Qwen3 running on AMD (vLLM + ROCm on MI300X) generates 8 candidate JSON plans, and all 8 run in parallel in MuJoCo with a Franka Panda arm. A scorer rejects unsafe plans, and Pixtral (also on AMD) checks the final camera image. The operator sees a score table and the best plan's video, then clicks Approve to export the robot program. Nothing runs on the real robot until a human approves it.

Built for the AMD Developer Hackathon: ACT III, Track 1 (Intelligent Industry).

## Team: Visionary Creators

- Anish Jaiswal ([@anish-01](https://github.com/anish-01)): AI, AMD, backend
- Shailesh ([@shaileshkryadav](https://github.com/shaileshkryadav)): robot sim, UI

## Task board

- [SimToReal Build project board](https://github.com/users/anish-01/projects/3) (all tasks by day and status)
- [Issues](https://github.com/anish-01/simtoreal-agent/issues) · [Milestones](https://github.com/anish-01/simtoreal-agent/milestones)

## Setup

Day 1 simulation setup (Python 3.12):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-sim.txt pytest==9.1.1
.venv/bin/python -m pytest -q
.venv/bin/python scripts/day1_demo.py --image runs/day1_final.png
```

Each candidate plan should own a fresh `actions.Robot` and stop on any `ok=False` result. See [Day 1 implementation notes](docs/day1_actions.md) for behavior, rationale, validation and alternatives. The scene and controller run locally without an AMD endpoint.
