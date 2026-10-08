# SimToReal Agent

**Test before you touch.** A factory operator types a robot task in plain English (e.g. "put the red part in bin A"). Qwen3 running on AMD (vLLM + ROCm on MI300X) generates 8 candidate JSON plans, and all 8 run in parallel in MuJoCo with a Franka Panda arm. A scorer rejects unsafe plans, and Pixtral (also on AMD) checks the final camera image. The operator sees a score table and the best plan's video, then clicks Approve to export the robot program. Nothing runs on the real robot until a human approves it.

Built for the AMD Developer Hackathon: ACT III, Track 1 (Intelligent Industry).

## Team: Visionary Creators

- Anish Jaiswal ([@anish-01](https://github.com/anish-01)): AI, AMD, backend
- Shailesh ([@shaileshkryadav](https://github.com/shaileshkryadav)): robot sim, UI

## Setup

Setup coming soon.
