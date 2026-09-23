from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent


def load_prompt(name):
    return (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")


def render_prompt(name, **values):
    text = load_prompt(name)
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text
