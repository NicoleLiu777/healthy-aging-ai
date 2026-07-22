from prompts import load_research_prompt
from llm import ask_llm


def main():

    question = input(
        "Enter your research question:\n> "
    )

    prompt = load_research_prompt(question)

    answer = ask_llm(prompt)

    print("\nQuestion:")
    print(question)

    print("\nAnswer:")
    print(answer)


if __name__ == "__main__":
    main()