# Healthy Aging Research Assistant

An AI-powered research assistant that generates evidence-based healthy aging summaries using Large Language Models.

## Overview

Healthy Aging Research Assistant uses GPT-based language models to answer research questions related to aging science, exercise, sleep, nutrition, and health.

The project demonstrates a complete LLM application pipeline:

User Question → Prompt Template → LLM API → Structured Research Report


## Features

- OpenAI LLM integration
- Environment-based configuration
- Prompt template management
- Structured research output
- Interactive user input
- Error handling
- Reproducible dependency setup

## Architecture

```text
User
 |
 v
main.py
 |
 v
Prompt Template
 |
 v
LLM Interface
 |
 v
OpenAI GPT Model
 |
 v
Research Report


## Tech Stack

- Python
- OpenAI API
- python-dotenv
- Git/GitHub


## Setup

Clone the repository:

git clone https://github.com/NicoleLiu777/healthy-aging-ai.git

cd healthy-aging-ai
Create virtual environment:
```markdown
```bash
python -m venv .venv

Install dependencies:
```markdown
```bash
pip install -r requirements.txt

Environment Variables
Create a .env file:

OPENAI_API_KEY=your_api_key
MODEL_NAME=gpt-4.1-mini

Run
```markdown
```bash
python app/main.py

Example:
Enter your research question:

How does sleep affect healthy aging?

The assistant generates an evidence-based research summary.

Project Status

Current version:
MVP - LLM Research Assistant

Future improvements will include document retrieval and RAG-based knowledge augmentation.


