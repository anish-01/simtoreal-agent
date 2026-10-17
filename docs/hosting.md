# Hosting the working app on Render

The repository includes a Dockerfile and a Render Blueprint with `plan: free`.
Render hosts Gradio and CPU simulation; AI inference stays on AMD Token Factory.
No paid hardware or subscription is configured by these files.

## Deployment

1. Sign in at https://dashboard.render.com and create a Blueprint from this
   repository and the branch containing `render.yaml`.
2. Confirm the service plan is **Free**. The blueprint uses Docker and asks for
   `LLM_API_KEY`; enter the team's AMD key as a secret, never as source code.
3. Deploy, then open the actual service URL returned by Render.
4. Check all three examples, video playback, human-review acknowledgement and
   both approval downloads on that URL. Only call the deployment verified after
   real simulations finish on the host.

An alternative is **New → Web Service → Public Git Repository**, with this
repository URL, Docker runtime, the deployment branch, and the Free plan. Add
the same environment variables from `render.yaml` manually in that flow.

## Runtime choices

- Python 3.12, pinned app dependencies, Mesa/OSMesa software rendering, and FFmpeg
  support headless simulation and H.264 videos without a GPU in the container.
- The app binds to Render's injected `PORT` on `0.0.0.0`.
- One simulation worker and single-threaded numeric/rendering libraries reduce
  CPU and memory contention on a small host. Eight candidates are still tested,
  one worker at a time. The existing worker timeout still applies to the batch.
- `serve.py` imports Gradio only in its main process, so spawned simulation
  workers do not load a second UI server.
- `.dockerignore` excludes credentials, virtual environments, Git history,
  recorded runs and exports from the image build context.

Free hosting sleeps after 15 minutes without incoming traffic and usually takes
about one minute to wake. Files are ephemeral: download exports before the
service restarts or sleeps. Free quotas and resource limits still apply. If a
full run exceeds the host's memory/time budget, the deployment needs adjustment;
do not silently upgrade to paid resources.

## Optional local container check

```sh
docker build -t simtoreal-agent .
docker run --rm -p 7860:7860 --env-file .env simtoreal-agent
```

The Docker engine was unavailable for local testing during preparation. Native
Python checks verify the UI and launcher, but cannot prove the Linux image
builds or that Render has enough memory. These must be verified at deployment.

References: https://render.com/docs/free and
https://render.com/docs/blueprint-spec.
