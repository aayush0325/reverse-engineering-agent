import os
import time
import logging
from typing import Any, Optional
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from groq import RateLimitError as GroqRateLimitError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLM")

# Global configuration for provider preference
# This can be set by the main script
_provider = os.getenv("LLM_PROVIDER", "groq").lower()
_model = os.getenv("LLM_MODEL")

def set_llm_config(provider: str, model: Optional[str] = None):
    """Sets the global LLM provider and model."""
    global _provider, _model
    _provider = provider.lower()
    _model = model

def get_llm(temperature: float = 0.0) -> Any:
    """
    Returns a configured LangChain LLM instance based on the provider.
    """
    provider = _provider
    model = _model
    
    if provider == "groq":
        model_name = model or "llama-3.3-70b-versatile"
        return ChatGroq(
            model=model_name,
            temperature=temperature,
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            max_retries=5
        )
    elif provider == "gemini" or provider == "google":
        model_name = model or "gemini-2.5-flash"
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            max_retries=5
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def invoke_llm_with_retry(chain: Any, inputs: dict, max_retries: int = 3) -> Any:
    """
    Invokes a LangChain chain with explicit retry logic for rate limits.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            return chain.invoke(inputs)
        except Exception as e:
            attempt += 1
            
            # Handle Groq Rate Limits
            if "RateLimitError" in str(type(e)) and "groq" in _provider:
                wait_time = 2  # Default wait
                if hasattr(e, 'response') and e.response is not None:
                    retry_after = e.response.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            pass
                logger.warning(f"Groq Rate limit hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            # Handle Google (Gemini) Rate Limits
            # Google GenAI uses the 'google.api_core.exceptions.ResourceExhausted' or similar
            if "ResourceExhausted" in str(type(e)) or "429" in str(e):
                wait_time = 10 * attempt # Exponential-ish backoff for Google
                logger.warning(f"Gemini Rate limit hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            # If we've reached max retries or it's a different error, raise it
            if attempt >= max_retries:
                logger.error(f"Max retries reached or fatal error: {str(e)}")
                raise e
            
            logger.error(f"LLM invocation failed (attempt {attempt}/{max_retries}): {str(e)}")
            time.sleep(2) # Default small wait for other errors
