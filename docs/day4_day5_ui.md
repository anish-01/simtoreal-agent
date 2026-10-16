# Days 4–5: operator interface and approval exports

Implements #28, #29, #33 and the page placement for #30. The backend already
supplies the AMD fields through #27. Optional obstacle work (#34) is deferred.
The team release freeze (#35) requires review, merging, main-branch demo checks,
and a joint release decision; this change does not tag an unmerged release.

## Data and approval flow

`app.py` calls `pipeline.run_task(task, n=8, scene=..., progress=...)`. The three
buttons use `DEMO_TASKS`; the impossible example switches the scene as well as
the text. Original backend results remain in server-side Gradio session state.
The page renders `table`, `best.result` media, `best.vision`, `amd`, and `timings`.
Model text is escaped before HTML rendering. Only existing media within this
application's `runs/` directory is exposed through page components.

Inputs and example buttons are disabled during a run. Previous results, approval,
acknowledgement and downloads are cleared before work starts. Input edits and
example selection also invalidate the result. An empty task does not call the
backend; endpoint/setup errors produce a retry message and disabled approval.

Approval uses the session's selected plan, rechecks simulation safety and plan
validation, and requires acknowledgement if vision needs review or is absent.
It writes unique export folders so approvals cannot overwrite one another.
It exports JSON and numbered readable steps without commanding hardware.

## Validation

Install `requirements-ui.txt` plus `pytest==9.1.1`, then run:

```sh
.venv/bin/python -m pytest -q
```

111 tests pass on macOS with Python 3.12.14 and Gradio 6.30.0. macOS rendering
needs graphics access. The 17 added tests cover approval metadata and steps,
collision/drop/failed-step rejection, missing and invalid plans, uncertain vision,
session resets, endpoint failure messages, scene selection, escaped output,
media confinement, and constructing the actual Gradio event graph.

Local browser checks with saved plans also verified eight red placements,
playback advancing through the H.264 best-plan video, all eight gallery images,
refusal to export before human review, and both downloads appearing after
approval. The out-of-reach example rejected all eight candidates, showed no best
video, and disabled approval. Switching examples cleared the prior downloads and
restored the correct scene.
All eight sorting candidates also passed through the page with a 13-second
best-plan video and all eight final images. The narrow-screen gallery uses two
columns to keep every thumbnail accessible.

Live AMD Token Factory endpoints are now configured in a private, Git-ignored
`.env`. The public `.env.tokenfactory.example` contains the shared URL and tested
model IDs with an empty key. Planning uses `DeepSeek-V4-Flash`; image verification
uses `DeepSeek-V4.1-Flash`. These are shared hosted services: the GPU SKU and
server software versions are not exposed. See `docs/benchmarks.md` for the live
run measurements and vision-review limitations. Saved-plan browser checks
exercise physics and media without measuring model inference. The optional
obstacle demo, friend usability review and team-wide freeze remain separate.

## Team handoff

Configure both model endpoints in `.env`, run `python app.py`, and test all three
examples against the AMD deployment. Check videos in Safari and on a phone.
For a disagreeing vision check, inspect the video and image, acknowledge review,
then approve. Confirm both downloads contain that run's plan and metadata.
Try an empty task and stopped model server; previous approval must stay cleared.
Only claim AMD numbers after a live run; the panel reads the returned values.
