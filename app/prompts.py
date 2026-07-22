from pathlib import Path


PROMPT_PATH = Path(__file__).parent / "prompts" / "research_prompt.txt"


def load_research_prompt(question):
    template = PROMPT_PATH.read_text()

    return template.format(
        question=question
    )