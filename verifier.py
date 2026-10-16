"""Verifier: checks the final camera image with Pixtral on AMD."""
import base64
import json
import os
import re
import time

# How each name looks from the top camera (checked against final.png images).
LOOKS = {'red_part': 'red cube', 'blue_part': 'blue cube',
         'bin_a': 'green bin at the bottom of the picture',
         'bin_b': 'green bin at the top of the picture'}


def question(goals):
    """Turn {'red_part': 'bin_a'} into a plain question about the picture."""
    asks = ' '.join(f'Is the {LOOKS[part]} inside the {LOOKS[bin_name]}?' for part, bin_name in goals.items())
    return (f'{asks} Answer "yes" only if every part asked about is inside its bin. Reply only with JSON: '
            '{"answer": "yes" or "no", "confidence": 0 to 1, "reason": "short"}')


def read_json(text):
    """Pull the first {...} out of the reply. None if it can't be read."""
    match = re.search(r'\{.*\}', text or '', re.S)
    try:
        return json.loads(match.group()) if match else None
    except json.JSONDecodeError:
        return None


def verify(image_path, goals, sim_success):
    """Ask Pixtral about the final image. needs_review is True if it disagrees with the sim or can't answer."""
    check = dict(answer='unknown', confidence=0., reason='', needs_review=True, seconds=0.)
    start = time.perf_counter()
    try:
        from dotenv import load_dotenv
        from openai import OpenAI
        load_dotenv()
        vlm = OpenAI(base_url=os.environ['VLM_BASE_URL'], api_key=os.getenv('LLM_API_KEY') or 'EMPTY')
        with open(image_path, 'rb') as f:
            picture = base64.b64encode(f.read()).decode()
        reply = vlm.chat.completions.create(
            model=os.getenv('VLM_MODEL') or 'mistralai/Pixtral-12B-2409',
            messages=[{'role': 'user', 'content': [
                {'type': 'text', 'text': question(goals)},
                {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{picture}'}}]}],
            temperature=0, max_tokens=150)
        found = read_json(reply.choices[0].message.content)
    except Exception as exc:
        check['reason'] = f'vision check failed: {exc}'
        return check
    finally:
        check['seconds'] = round(time.perf_counter() - start, 3)
    if not found or found.get('answer') not in ('yes', 'no'):
        check['reason'] = 'could not read the vision reply'
        return check
    check.update(answer=found['answer'], confidence=found.get('confidence', 0.), reason=found.get('reason', ''))
    check['needs_review'] = (found['answer'] == 'yes') != bool(sim_success)
    return check
