from app.prompts import load_research_prompt


def test_prompt_loading():
    prompt = load_research_prompt(
        "How does sleep affect healthy aging?"
    )

    assert "sleep" in prompt.lower()