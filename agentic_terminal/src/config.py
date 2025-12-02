import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "google/gemini-2.0-flash-001")
    
    # Cost per 1M tokens (approximate for Gemini 2.0 Flash)
    # Adjust these based on actual OpenRouter pricing
    INPUT_COST_PER_1M = 0.10  # $0.10 per 1M input tokens
    OUTPUT_COST_PER_1M = 0.40 # $0.40 per 1M output tokens

    @classmethod
    def validate(cls):
        if not cls.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not set in environment variables.")
