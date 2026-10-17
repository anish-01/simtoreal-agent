"""Container entry point; avoid importing Gradio in spawned simulation workers."""
import os
from pathlib import Path


def main():
    # Imports stay inside main: multiprocessing reimports this file in each worker.
    from dotenv import load_dotenv
    load_dotenv()
    from app import build_app, CSS

    root = Path(__file__).resolve().parent
    for name in ('runs', 'exports'):
        (root / name).mkdir(exist_ok=True)
    port = int(os.getenv('PORT') or os.getenv('GRADIO_SERVER_PORT') or '7860')
    build_app().queue(max_size=4).launch(
        server_name=os.getenv('GRADIO_SERVER_NAME', '127.0.0.1'),
        server_port=port,
        allowed_paths=[str(root / 'runs'), str(root / 'exports')],
        max_threads=8, css=CSS)


if __name__ == '__main__':
    main()
