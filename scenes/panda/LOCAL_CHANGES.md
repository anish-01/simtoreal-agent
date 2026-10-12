# Panda model provenance and local modifications

Source: https://github.com/google-deepmind/mujoco_menagerie/tree/0059d4335f8156206f63a35662313385f7ad6d74/franka_emika_panda
License: Apache 2.0, retained in LICENSE. Meshes are unchanged.

panda.xml changes for SimToReal Agent:
- Removed the built-in home keyframe so loose cube joints do not invalidate its qpos dimension. Joint values are preserved in actions.HOME.
- Added a site named tcp at hand-local position 0 0 0.103 between the fingertips.
- Replaced compiler meshdir with explicit assets/ paths, supporting standalone IK loading and factory inclusion.

The factory scene is authored for this project. Other upstream XML files are retained as reference and are not the scene used by actions.py.
