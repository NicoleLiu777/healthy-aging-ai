from llm import ask_llm
from prompts import load_research_prompt


question = "What are the benefits of resistance training for older adults?"


prompt = load_research_prompt(question)


answer = ask_llm(prompt)


print("Question:")
print(question)

print("\nAnswer:")
print(answer)