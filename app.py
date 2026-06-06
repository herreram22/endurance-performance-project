from pathlib import Path
import runpy


APP_ENTRYPOINT = Path(__file__).parent / "app" / "app.py"

runpy.run_path(str(APP_ENTRYPOINT), run_name="__main__")
