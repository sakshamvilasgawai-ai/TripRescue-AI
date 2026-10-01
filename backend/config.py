import os

from dotenv import load_dotenv


load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

try:
    MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "12"))
except ValueError:
    MAX_AGENT_STEPS = 12