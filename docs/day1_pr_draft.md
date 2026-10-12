# Implement bounded Panda simulation actions for Day 1

The action module was empty, so planner steps could not move a simulated robot. This change adds independent `Robot` instances with move_to, grasp, release, lift and home. Actions return `{ok, reason}`, reject invalid or unreachable targets, and share a four-second simulated-time limit. Grasp success requires physical finger contact and actual cube lift.

Includes the missing factory scene and licensed Panda assets required to exercise the actions, pinned dependencies, a demo script and implementation notes. The controller uses arm-only mink IK and physical MuJoCo actuators.

Validation: 24 pytest cases passed, including both colors picked and deposited into their respective bins, all five timeout paths, bad targets, solver failure and instance isolation. The red demo and overhead render also passed.

Review limits: this is the simulation action layer. Motion is not certified collision-free; simulated-time timeout does not bound a stalled native solver. Model serving, planner integration and the later simulator/scorer remain separate tasks.

Closes #16
