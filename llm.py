
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")

# Use gemini-3.5-flash-lite or gemini-3.5-flash: active, fast, free-tier models with separate daily quota.
# Note: Google model names must use hyphens (no spaces).
# api_version="v1beta" is required for JSON mode and structured output in Google GenAI SDK.
model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

llm = ChatGoogleGenerativeAI(
    model=model_name,
    api_key=api_key,
    api_version="v1beta",
    timeout=45,
    max_retries=1,
)
