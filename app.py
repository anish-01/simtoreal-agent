"""Operator page. Run with python app.py; model endpoints come from .env."""
import html
import logging
import os
from pathlib import Path

import gradio as gr
import pipeline
from demo_tasks import DEMO_TASKS
from exporter import export_approved

ROOT = Path(__file__).resolve().parent
SCENES = {'Factory': DEMO_TASKS['easy']['scene'],
          'Blue part out of reach': DEMO_TASKS['unreachable']['scene']}
CSS = """
.gradio-container {max-width:1200px !important;}
.score-table {width:100%; border-collapse:collapse; margin:1rem 0;}
.score-table th,.score-table td {padding:.7rem; text-align:left; border-bottom:1px solid #aaa; overflow-wrap:anywhere;}
.score-table .accepted {color:#166534; background:#f0fdf4;}
.score-table .rejected {color:#991b1b; background:#fef2f2;}
.score-table .best {border-left:5px solid #15803d; font-weight:600;}
.safety-banner {padding:1rem; border:1px solid #15803d; border-radius:12px; background:#f0fdf4; color:#14532d;}
@media (max-width:600px) {#candidate-gallery .grid-container {--grid-cols:2 !important;}}
"""


def score_table(result):
    """Escape model text before adding operator-facing row colors."""
    rows = []
    best = (result.get('best') or {}).get('plan_id')
    for row in result.get('table', []):
        accepted = row['status'] == 'OK'
        selected = accepted and row['plan_id'] == best
        values = [f"{'★ Best · ' if selected else ''}{row['plan_id']}", row['score'],
                  'OK' if accepted else 'Rejected', row['reason']]
        cells = ''.join(f'<td>{html.escape(str(value))}</td>' for value in values)
        classes = ('accepted' if accepted else 'rejected') + (' best' if selected else '')
        rows.append(f'<tr class="{classes}">{cells}</tr>')
    return ('<table class="score-table"><caption>Simulation results · scores out of 100</caption>'
            '<thead><tr><th>Plan</th><th>Score</th><th>Status</th><th>Reason</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def metrics(result):
    amd, timings = result.get('amd', {}), result.get('timings', {})
    rows = [('GPU', amd.get('gpu', 'Not reported')),
            ('Planner model', amd.get('llm_model', 'Not reported')),
            ('Vision model', amd.get('vlm_model', 'Not reported')),
            ('Planning time (s)', timings.get('llm_s', 'Not reported')),
            ('Plans per second', amd.get('plans_per_s', 'Not reported')),
            ('Simulation time (s)', timings.get('sim_s', 'Not reported')),
            ('Vision time (s)', timings.get('vision_s', 'Not reported')),
            ('Total time (s)', timings.get('total_s', 'Not reported'))]
    return '<table class="score-table">' + ''.join(
        f'<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>'
        for label, value in rows) + '</table>'


def media_path(value):
    if not value:
        return None
    path = Path(value).resolve()
    return str(path) if path.is_relative_to(ROOT / 'runs') and path.is_file() else None


def presentation(result):
    best = result.get('best')
    safe = bool(best and best.get('status') == 'OK')
    vision = (best or {}).get('vision') or {}
    needs_review = safe and vision.get('needs_review', True)
    status = result.get('error') or ('Simulation passed. Review the video, then approve the export.' if safe else 'No safe plan found.')
    vision_text = 'No best plan to check.'
    if safe:
        reason = str(vision.get('reason') or vision.get('answer', 'Not available'))
        if reason.startswith('vision check failed:'):
            reason = 'The camera check is unavailable. Inspect the video and final image.'
        vision_text = ('Needs human review. ' if needs_review else 'Vision check: ') + reason
    gallery = [(path, f"Plan {row['plan_id']} · {row['status']}")
               for row in result.get('table', [])
               if (path := media_path(row.get('result', {}).get('image_path')))]
    return (result, status, score_table(result),
            media_path((best or {}).get('result', {}).get('video_path')), gallery,
            vision_text, metrics(result), gr.update(interactive=safe),
            gr.update(value=False, visible=bool(needs_review)), None, '')


def cleared():
    return (None, 'Ready. Choose an example or describe where the parts should go.',
            '', None, [], '', '', gr.update(interactive=False),
            gr.update(value=False, visible=False), None, '')


def run_task(task, scene, progress=gr.Progress()):
    initial = list(cleared())
    initial[1] = 'Testing plans…'
    yield (*initial, *[gr.update(interactive=False) for _ in range(6)])
    try:
        if not task or not task.strip():
            result = list(cleared())
            result[1] = 'Enter a task, such as “Put the red part in bin A”.'
        else:
            response = pipeline.run_task(task.strip(), scene=SCENES[scene],
                                         progress=lambda f, m: progress(f, desc=m))
            result = presentation(response)
    except Exception:
        logging.exception('Task run failed')
        result = list(cleared())
        result[1] = 'The task could not finish. Check that the configured model servers are available, then try again.'
    yield (*result, *[gr.update(interactive=True) for _ in range(6)])


def approve(result, reviewed):
    try:
        paths = export_approved(result, reviewed=reviewed)
        return [str(path) for path in paths], 'Exported the approved JSON and readable steps. No robot was connected or commanded.'
    except ValueError as exc:
        return None, str(exc)
    except OSError:
        logging.exception('Export failed')
        return None, 'The export could not be saved. Check export-folder permissions and try again.'


def build_app():
    with gr.Blocks(title='SimToReal Agent') as app:
        gr.Markdown('# SimToReal Agent\nTest before you touch.')
        gr.HTML('<div class="safety-banner">Nothing runs on the real robot until you approve.</div>')
        gr.Markdown('This demo tests a simulated robot and exports a plan for review. It does not connect to a real robot.')
        state = gr.State(None)
        task = gr.Textbox(label='What should the robot do?', placeholder='Put the red part in bin A',
                          info='Name a part and a bin. Try “Sort both parts by color”.')
        with gr.Row():
            buttons = [gr.Button(label) for label in ['Red to bin A', 'Sort both parts', 'Try an out-of-reach part']]
        scene = gr.Dropdown(list(SCENES), value='Factory', label='Simulation scene',
                            info='The third example puts the blue part outside the arm’s reach.')
        run = gr.Button('Test 8 plans in simulation', variant='primary')
        status = gr.Textbox(label='Run status', value=cleared()[1], interactive=False)
        table = gr.HTML()
        with gr.Row():
            video = gr.Video(label='Best plan · watch before approving', interactive=False)
            gallery = gr.Gallery(label='All candidate final images', columns=4, height=320,
                                 elem_id='candidate-gallery', interactive=False,
                                 buttons=['download', 'download_all', 'fullscreen'])
        vision = gr.Textbox(label='Camera check', interactive=False)
        reviewed = gr.Checkbox(label='I reviewed the video and final image despite the uncertain or disagreeing camera check.', visible=False)
        approval = gr.Button('Approve and export this plan', interactive=False, variant='primary')
        files = gr.File(label='Download approved program', file_count='multiple', interactive=False)
        export_status = gr.Textbox(label='Export status', interactive=False)
        with gr.Accordion('AMD run metrics', open=True):
            amd = gr.HTML()
            gr.Markdown('Values above are reported by the backend for this run. GPU identity comes from the server configuration.')
        gr.Markdown('Models served by AMD Token Factory (shared AMD GPU service; GPU model not reported)')
        outputs = [state, status, table, video, gallery, vision, amd, approval, reviewed, files, export_status]
        controls = [task, scene, run, *buttons]
        run.click(run_task, [task, scene], [*outputs, *controls], concurrency_limit=1,
                  concurrency_id='simulation', api_visibility='private', show_progress_on=status)
        task.input(cleared, outputs=outputs, queue=False, api_visibility='private')
        scene.input(cleared, outputs=outputs, queue=False, api_visibility='private')
        for button, (name, demo) in zip(buttons, DEMO_TASKS.items()):
            def example(text=demo['task'], selection='Blue part out of reach' if name == 'unreachable' else 'Factory'):
                return text, selection, *cleared()
            button.click(example, outputs=[task, scene, *outputs], queue=False, api_visibility='private')
        approval.click(approve, [state, reviewed], [files, export_status], api_visibility='private')
    return app


if __name__ == '__main__':
    build_app().queue(max_size=8).launch(
        server_name=os.getenv('GRADIO_SERVER_NAME', '127.0.0.1'),
        server_port=int(os.getenv('GRADIO_SERVER_PORT', '7860')),
        allowed_paths=[str(ROOT / 'runs'), str(ROOT / 'exports')], css=CSS)
