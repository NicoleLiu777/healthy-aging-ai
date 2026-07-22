from llm import ask_llm


question = "What are the benefits of resistance training for older adults?"


answer = ask_llm(question)


print("Question:")
print(question)

print("\nAnswer:")
print(answer)