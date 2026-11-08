
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0.7,
    max_retries=2
)
