from openai import OpenAI
from config import MODEL_NAME

client = OpenAI()


def ask_llm(prompt):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error: Unable to get response from AI service. {e}"