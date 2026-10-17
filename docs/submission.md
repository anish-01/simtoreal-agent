# Submission kit: AMD Developer Hackathon ACT III

Everything to paste into the lablab.ai form (#46), the descriptions (#38) and the voiceover script (#44).
Every number here was measured; see [benchmarks](benchmarks.md).

## Form fields

| Field | Value |
| --- | --- |
| Project title | SimToReal Agent |
| Track | Track 1: Intelligent Industry |
| Team | Visionary Creators (Anish Jaiswal, Shailesh) |
| Public GitHub repository | https://github.com/anish-01/simtoreal-agent |
| Demo application platform | Render (Docker, free plan) |
| Application URL | https://simtoreal-agent.onrender.com |
| Cover image | `cover.png` from https://github.com/shaileshkryadav/simtoreal-agent-demo |
| Slide presentation | `SimToReal-Agent-Slides.pdf` from the same repository |
| Video presentation | Final edited video with voiceover (#45); upload to YouTube as *Unlisted* and paste the link |

## Short description

AI on AMD Token Factory writes eight robot programs for a factory task; MuJoCo tests each one, unsafe plans are rejected with a reason, and an operator approves the best before export.

## Long description

**Problem.** Changing what a robot cell does is slow and risky. An AI can write a robot program in seconds, but a program that looks valid can still drop a part, hit the table or reach for something out of range. On a real line that means scrapped parts, damaged tooling and downtime, so nobody should run an untested AI program on a real machine.

**User.** The cell operator or automation engineer who re-tasks a robot and has to sign off that a new program is safe.

**How it works.** The operator types a task such as "Sort both parts by color". An LLM on AMD Token Factory turns it into explicit goals and writes eight candidate pick-and-place programs, each checked against the allowed actions and objects. All eight run in parallel in a MuJoCo simulation of a Franka Panda arm, which records a video, a final camera image, collisions and dropped parts. A safety-first scorer rejects every program that collides, drops a part, fails a step or misses the goal, and ranks the rest. A vision model on AMD then checks the best program's final image; if it disagrees with the simulator or cannot tell, the plan is flagged for human review. The operator watches the evidence, acknowledges any flag and approves. Only then are the program and readable steps exported. The app never commands a real robot.

**AMD.** All model inference runs on AMD Token Factory: DeepSeek-V4-Flash reads the task and writes the plans, and DeepSeek-V4.1-Flash reviews the camera image. Each run shows an AMD panel with the models, planning, vision and simulation times, and plans per second, taken from that run.

**Results.** In live runs on AMD Token Factory, 24 AI-written programs for three tasks were tested: 12 passed and 12 unsafe or impossible ones were caught in simulation before reaching a robot, each with a readable reason. For a part placed out of reach, all eight programs were rejected and the app refused to offer any. Planning eight programs took 6–8 seconds. In both successful tasks the robot arm hid the bin from the camera, and the app correctly required a person to check before approval.

**Next.** Clearer camera views, full path collision checks and a pilot on a real cell.

## Technology tags

Use the closest options the form offers. Only list what the project really uses:

AMD Token Factory · AMD · DeepSeek · MuJoCo · Gradio · Python · Docker · Render · Robotics · Simulation

Do **not** tag AMD Developer Cloud, ROCm, vLLM, Llama 3.1 or Pixtral: they were the original plan but are not part of the submitted product.

## Voiceover script (about 70 seconds)

Read it slowly over the demo video. Timings follow #44.

**Problem (20 s).**
"Changing what a factory robot does is slow and risky. AI can now write a robot program in seconds, but a program that looks right can still drop a part or reach for something it can't get to. On a real line, that's scrap, broken tools and downtime."

**User (10 s).**
"SimToReal Agent is for the operator who has to sign off a new robot program. Our rule is simple: test before you touch."

**AMD (20 s).**
"The operator types a task. AI models on AMD Token Factory turn it into goals and write eight candidate programs in a few seconds. Every program is then tested in a physics simulation, and a vision model on AMD double-checks the final camera image."

**Impact (20 s).**
"In our live runs, twelve of twenty-four AI programs were unsafe or impossible, and every one was caught in simulation with a clear reason, before touching a robot. When the camera wasn't sure, the app asked a human to check. Nothing is exported until the operator approves."

## Final check (#47)

- [ ] Watch the final video once together; the voice matches the screen
- [ ] Open every link above from a phone, including the live app (wait up to a minute for it to wake)
- [ ] The live app footer says "Models served by AMD Token Factory"
- [ ] Submit before the deadline and screenshot the confirmation
