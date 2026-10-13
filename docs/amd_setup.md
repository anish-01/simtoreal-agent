# AMD setup: serving the models on MI300X

How to run both models on one AMD Instinct MI300X (AMD Developer Cloud) with vLLM on ROCm.

| Role | Model | Port | Env var in `.env` |
| --- | --- | --- | --- |
| Planner | `meta-llama/Llama-3.1-8B-Instruct` | 8000 | `LLM_BASE_URL=http://localhost:8000/v1` |
| Vision checker | `mistralai/Pixtral-12B-2409` | 8001 | `VLM_BASE_URL=http://localhost:8001/v1` |

Target: from a fresh VM to both servers answering in under 30 minutes.

## 0. Before Day 1 (one time)

1. Create a Hugging Face **Read** token: https://huggingface.co/settings/tokens
2. Fill in Meta's licence form on https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct with the same Hugging Face account as the token. Llama is gated; without approval the download fails with a "gated repo" error, and approval can take a little while, so do it early. Check https://huggingface.co/settings/gated-repos for "accepted".
   - Pixtral (https://huggingface.co/mistralai/Pixtral-12B-2409) is not gated: nothing to accept.
3. Have an SSH key ready (`ls ~/.ssh/id_ed25519.pub`, or create one with `ssh-keygen -t ed25519`).

## 1. Start the VM

1. In the AMD Developer Cloud console, create a VM with **1× MI300X**. If a ROCm or vLLM quick-start image is offered, pick it (Docker and ROCm drivers are preinstalled). Add your SSH public key.
2. Write down the hourly price. **Stop or destroy the VM when you are not using it**: credits are charged by the hour.
3. Log in and check the GPU:

```sh
ssh root@<VM_IP>          # use the user name the console shows
rocm-smi                  # or: amd-smi
```

Save a screenshot of the output for the slides (`docs/img/rocm-smi.png`).

## 2. Pull the vLLM ROCm image

AMD publishes prebuilt vLLM images for MI300X as `rocm/vllm`. Check the newest tag on the ROCm docs page **"vLLM inference"** (https://rocm.docs.amd.com, use the current version, not an archived one) or on Docker Hub, and pin it:

```sh
export VLLM_IMAGE=rocm/vllm:latest   # replace latest with the exact tag you checked
export HF_TOKEN=hf_xxx               # your Read token
docker pull $VLLM_IMAGE
mkdir -p ~/.cache/huggingface
```

## 3. Start both servers

Both models share one GPU, so each gets 40% of its memory (`--gpu-memory-utilization 0.40`). Without that, the first server takes almost everything and the second fails with out-of-memory. `--max-model-len` stops each server reserving memory for a huge context we don't need.

```sh
# Planner: Llama 3.1 8B on port 8000
docker run -d --name llama \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --ipc=host --shm-size 16g --security-opt seccomp=unconfined \
  -p 127.0.0.1:8000:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface -e HF_TOKEN \
  $VLLM_IMAGE \
  vllm serve meta-llama/Llama-3.1-8B-Instruct --host 0.0.0.0 --port 8000 \
  --max-model-len 8192 --gpu-memory-utilization 0.40

# Vision checker: Pixtral-12B on port 8001 (needs the three Mistral-format flags)
docker run -d --name pixtral \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --ipc=host --shm-size 16g --security-opt seccomp=unconfined \
  -p 127.0.0.1:8001:8001 \
  -v ~/.cache/huggingface:/root/.cache/huggingface -e HF_TOKEN \
  $VLLM_IMAGE \
  vllm serve mistralai/Pixtral-12B-2409 --host 0.0.0.0 --port 8001 \
  --tokenizer-mode mistral --config-format mistral --load-format mistral \
  --max-model-len 16384 --gpu-memory-utilization 0.40
```

Start Llama first and wait until it is up before starting Pixtral, so the two don't fight over memory during start-up.

The first start downloads the weights (roughly 16 GB for Llama 3.1 8B and 25 GB for Pixtral). The mounted cache makes the next start much faster, as long as the VM disk is kept.

If the container exits straight away because the image has its own entrypoint, add `--entrypoint ""` before `$VLLM_IMAGE`.

## 4. Check they are running

```sh
docker logs -f llama      # wait for "Application startup complete", then Ctrl+C
docker logs -f pixtral
curl -s localhost:8000/v1/models
curl -s localhost:8001/v1/models
```

Test the planner with one JSON request:

```sh
curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model": "meta-llama/Llama-3.1-8B-Instruct",
  "messages": [{"role": "user", "content": "Reply with the JSON {\"ok\": true}"}],
  "response_format": {"type": "json_object"}
}'
```

Record the versions for `docs/benchmarks.md`:

```sh
docker exec llama vllm --version
rocm-smi --showdriverversion
```

## 5. Use the servers from your laptop

The servers are bound to `127.0.0.1` on the VM, so they are not open to the internet. Open an SSH tunnel and keep it running:

```sh
ssh -N -L 8000:localhost:8000 -L 8001:localhost:8001 root@<VM_IP>
```

Then in your local `.env`:

```sh
LLM_BASE_URL=http://localhost:8000/v1
VLM_BASE_URL=http://localhost:8001/v1
```

Check the planner prompt against AMD:

```sh
.venv/bin/python scripts/test_prompt.py
```

Never open ports 8000/8001 publicly. If they must be public (for example for a hosted UI elsewhere), start vLLM with `--api-key <secret>` and set `LLM_API_KEY` / `VLM_API_KEY` in `.env`.

## 6. Stop and restart

```sh
docker stop llama pixtral       # stop serving (VM still billed)
docker start llama pixtral      # start again later
docker rm -f llama pixtral      # remove before re-running the docker run commands
```

Stop the VM itself from the console when you are done for the day.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `gated repo` / 401 when loading a model | Accept Meta's terms on the Llama model page and wait for approval (Pixtral is not gated) and check `HF_TOKEN` is passed with `-e HF_TOKEN`. |
| Second server fails with out-of-memory | Lower `--gpu-memory-utilization` on both, or start them one after the other. |
| Planner replies with text around the JSON | The request is missing `response_format: {"type": "json_object"}`. `planner.parse` still extracts the JSON. |
| `curl` from the laptop hangs | The SSH tunnel isn't running, or the server is still loading (check `docker logs`). |
| Container can't see the GPU | Check `--device=/dev/kfd --device=/dev/dri --group-add video` and that `rocm-smi` works on the host. |

## Sources

- ROCm vLLM Docker docs: https://rocm.docs.amd.com/how-to/rocm-for-ai/inference/vllm-benchmark.html
- Pixtral with vLLM: https://docs.mistral.ai/self-deployment/vllm and https://huggingface.co/mistralai/Pixtral-12B-2409
- Llama 3.1 8B Instruct model card: https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
