"""D1.2: time the planner and vision servers on AMD and write docs/benchmarks.md."""
import argparse
import base64
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from openai import OpenAI
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import planner

TASK = 'Sort both parts by color: red part to bin A, blue part to bin B'


def timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


def bench_llm(runs):
    llm = planner.client()
    model = os.getenv('LLM_MODEL') or 'meta-llama/Llama-3.1-8B-Instruct'
    one = lambda: llm.chat.completions.create(
        model=model, temperature=.2, max_tokens=512, response_format={'type': 'json_object'},
        messages=[{'role': 'system', 'content': planner.SYSTEM_PROMPT}, {'role': 'user', 'content': TASK}])
    timed(one)  # warm-up, not counted
    samples = [timed(one) for _ in range(runs)]
    seconds = [s for _, s in samples]
    tokens = [r.usage.completion_tokens / s for r, s in samples]
    plans, eight = timed(lambda: planner.generate_plans(TASK, n=8, llm=llm))
    return model, statistics.mean(seconds), statistics.mean(tokens), eight, len(plans)


def bench_vlm(image, runs):
    from dotenv import load_dotenv
    load_dotenv()
    vlm = OpenAI(base_url=os.environ['VLM_BASE_URL'], api_key=os.getenv('VLM_API_KEY') or 'EMPTY')
    model = os.getenv('VLM_MODEL') or 'mistralai/Pixtral-12B-2409'
    url = 'data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode()
    one = lambda: vlm.chat.completions.create(model=model, temperature=0, max_tokens=100, messages=[{'role': 'user', 'content': [
        {'type': 'text', 'text': 'Top-down image of a robot work cell. Is the red cube inside a bin? Answer yes or no and one short reason.'},
        {'type': 'image_url', 'image_url': {'url': url}}]}])
    first, _ = timed(one)  # warm-up, not counted
    seconds = [timed(one)[1] for _ in range(runs)]
    return model, statistics.mean(seconds), first.choices[0].message.content.strip()


def write_section(heading, lines, path=ROOT / 'docs' / 'benchmarks.md'):
    """Replace (or add) one '## heading' section of docs/benchmarks.md, keeping the other sections."""
    text = path.read_text() if path.exists() else '# Benchmarks\n'
    parts = text.split('\n## ')
    section = f'{heading}\n\n' + '\n'.join(lines).strip() + '\n'
    kept = [part for part in parts[1:] if part.split('\n', 1)[0] != heading]
    path.write_text('\n## '.join([parts[0].rstrip() + '\n'] + kept + [section]))
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--image', type=Path, default=ROOT / 'runs' / 'p12.png', help='top_cam snapshot for the vision test')
    parser.add_argument('--skip-llm', action='store_true')
    parser.add_argument('--skip-vlm', action='store_true')
    args = parser.parse_args()

    lines = [f'Measured {datetime.now():%Y-%m-%d %H:%M} with `scripts/bench_models.py`. '
             f'Averages of {args.runs} requests after one warm-up request. Times include the SSH tunnel.\n',
             '| Measurement | Value |', '| --- | --- |']
    if not args.skip_llm:
        model, one, tps, eight, valid = bench_llm(args.runs)
        lines += [f'| Planner model | `{model}` |', f'| One plan | {one:.2f} s |', f'| Planner speed | {tps:.0f} tokens/s |',
                  f'| 8 plans in parallel | {eight:.2f} s ({valid}/8 valid) |', f'| Plans per second | {valid / eight:.1f} |']
    if not args.skip_vlm:
        model, check, answer = bench_vlm(args.image, args.runs)
        lines += [f'| Vision model | `{model}` |', f'| One image check | {check:.2f} s |']
        print('Vision answer:', answer)
    lines += ['', 'Fill in from the VM: GPU (`rocm-smi`), ROCm version, vLLM version (`docker exec llama vllm --version`).', '']
    out = write_section('Model serving (AMD)', lines)
    print('\n'.join(lines))
    print('Written to', out)


if __name__ == '__main__':
    raise SystemExit(main())
