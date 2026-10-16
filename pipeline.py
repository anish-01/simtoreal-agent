"""Backend pipeline: task -> goals -> 8 plans -> 8 parallel simulations -> ranked table -> best plan."""
import multiprocessing as mp
import os
import time
import planner
import runlog
import scorer
import verifier
from simulator import run_plan, SCENE

SIM_TIMEOUT = 180.


def _failed(plan, reason):
    """Result row in the simulator's format for a candidate whose worker never returned."""
    return dict(plan_id=plan.get('plan_id'), success=False, steps_done=0, time=0., collisions=0, dropped=False,
                failed_step=None, reason=reason, image_path=None, video_path=None)


def workers(n_plans):
    """Worker processes: SIM_WORKERS from the environment, else one per plan up to the CPU count (max 8).

    On an 8 GB M2 Mac, SIM_WORKERS=4 is faster than 8 (4 performance cores); the 20-vCPU AMD VM can use 8.
    """
    wanted = int(os.getenv('SIM_WORKERS') or min(os.cpu_count() or 1, 8))
    return max(1, min(n_plans, wanted))


def run_all(plans, goals, run_dir, parallel=True, scene=SCENE, timeout=SIM_TIMEOUT):
    """Simulate every plan in worker processes. A worker that exceeds the wall-clock timeout is reported as failed."""
    if not parallel:
        return [run_plan(p, goals, run_dir, scene=scene) for p in plans]
    ctx = mp.get_context('spawn')  # fresh interpreter per worker: no MuJoCo or renderer state is shared
    pool = ctx.Pool(processes=workers(len(plans)))
    try:
        jobs = [pool.apply_async(run_plan, (p, goals, str(run_dir)), {'scene': scene}) for p in plans]
        deadline = time.monotonic() + timeout
        results = []
        for plan, job in zip(plans, jobs):
            try:
                results.append(job.get(max(0., deadline - time.monotonic())))
            except mp.TimeoutError:
                results.append(_failed(plan, f'simulation timed out after {timeout:.0f} s'))
            except Exception as exc:
                results.append(_failed(plan, f'simulation crashed: {exc}'))
        return results
    finally:
        pool.terminate()
        pool.join()


def run_task(task, n=8, progress=None, llm=None, parallel=True, scene=SCENE, root=None):
    """One call for the UI. progress(fraction, message) is optional. Everything is saved in runs/<run_id>/ (or under root)."""
    report = progress or (lambda fraction, message: None)
    start = time.perf_counter()
    run_dir = runlog.new_run(task, root or runlog.RUNS)
    result = dict(run_id=run_dir.name, run_dir=str(run_dir), task=task, goals=None, plans=[], table=[],
                  best=None, error='', timings={})
    llm = llm or planner.client()

    report(.05, 'Reading the task…')
    goals, reason = planner.extract_goals(task, llm)
    if goals is None:
        result['error'] = reason
        return _finish(result, start)
    result['goals'] = goals
    runlog.save_json(run_dir, 'goals.json', goals)

    report(.15, f'Planning {n} candidates on AMD…')
    t = time.perf_counter()
    plans = planner.generate_plans(task, n=n, llm=llm)
    result['timings']['llm_s'] = round(time.perf_counter() - t, 3)
    result['plans'] = plans
    runlog.save_json(run_dir, 'plans.json', plans)
    if not plans:
        result['error'] = 'the planner returned no valid plans'
        return _finish(result, start)

    report(.35, f'Simulating {len(plans)} plans in parallel…')
    t = time.perf_counter()
    results = run_all(plans, goals, run_dir, parallel=parallel, scene=scene)
    result['timings']['sim_s'] = round(time.perf_counter() - t, 3)

    report(.9, 'Scoring…')
    result['table'] = scorer.score(results)
    result['best'] = next((row for row in result['table'] if row['status'] == 'OK'), None)
    if result['best'] is None:
        result['error'] = 'no safe plan found'
    else:
        report(.95, 'Checking the final image with Pixtral…')
        best = result['best']['result']
        result['best']['vision'] = verifier.verify(best['image_path'], goals, best['success'])
        result['timings']['vision_s'] = result['best']['vision']['seconds']
    report(1., 'Done')
    return _finish(result, start)


def _finish(result, start):
    result['timings']['total_s'] = round(time.perf_counter() - start, 3)
    result['amd'] = _amd(result)
    runlog.save_json(result['run_dir'], 'results.json', result)
    return result

def _finish(result, start):
    result['timings']['total_s'] = round(time.perf_counter() - start, 3)
    result['amd'] = _amd(result)
    runlog.save_json(result['run_dir'], 'results.json', result)
    return result


def _amd(result):
    """AMD proof for the UI: GPU and model names from settings, plus planning speed."""
    llm_s = result['timings'].get('llm_s')
    return dict(gpu=os.getenv('GPU_NAME') or 'unknown GPU',
                llm_model=os.getenv('LLM_MODEL') or 'meta-llama/Llama-3.1-8B-Instruct',
                vlm_model=os.getenv('VLM_MODEL') or 'mistralai/Pixtral-12B-2409',
                plans_per_s=round(len(result['plans']) / llm_s, 2) if llm_s else 0.)

