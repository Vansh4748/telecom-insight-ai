from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL


class LLMError(Exception):
    """Raised when the Gemini call cannot be completed."""


def generate(prompt: str, temperature: float = 0.2) -> str:
    """Send a prompt to Gemini and return the answer text."""
    if not GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set. Add it to your .env file.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature),
        )
    except Exception as e:
        raise LLMError(f"Gemini request failed: {e}") from e

    text = (response.text or "").strip()
    if not text:
        raise LLMError("Gemini returned an empty response (it may have been blocked).")
    return text