from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_NAME

client = OpenAI(
    api_key=OPENAI_API_KEY
)


def ask_llm(question):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": question
            }
        ]
    )

    return response.choices[0].message.content