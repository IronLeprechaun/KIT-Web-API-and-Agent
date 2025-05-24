import google.generativeai as genai
import os
import sys
import logging
from typing import List, Dict, Any, Optional, Tuple # Added for type hints
from pathlib import Path

# Add project root to sys.path to allow importing secrets manager
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

def get_api_key_from_secrets(password: Optional[str] = None) -> Optional[str]:
    """Load Gemini API key from secrets manager (no password required for local app)"""
    try:
        from secrets_manager import SecretsManager
        manager = SecretsManager()
        
        if not manager.secrets_file.exists():
            return None
            
        # Load from secrets manager (no password required)
        return manager.get_secret('GEMINI_API_KEY')
            
    except ImportError:
        # Secrets manager not available
        return None
    except Exception:
        # Failed to load secrets
        return None

class GeminiClient:
    def __init__(self, model_name: str = "gemini-1.5-pro-latest", logger: Optional[logging.Logger] = None, system_instruction: Optional[str] = None, api_key: Optional[str] = None):
        self.logger = logger if logger else logging.getLogger(__name__)
        self.model_name = model_name # Store model_name
        self.system_instruction = system_instruction # Store system_instruction
        
        # API key is no longer fetched or configured in __init__
        # It will be fetched and configured in send_prompt_async

        model_args = {}
        if self.system_instruction:
            model_args['system_instruction'] = self.system_instruction
            self.logger.info(f"Using system instruction for Gemini model: '{self.system_instruction[:100]}...'")

        # Initialize the model; API key will be configured per call in send_prompt_async
        self.model = genai.GenerativeModel(self.model_name, **model_args)
        self.logger.info(f"GeminiClient initialized with model: {self.model_name}. API key will be configured on send.")

    async def send_prompt_async(self, conversation_history: List[Dict[str, Any]]) -> str:
        """
        Sends a conversation history to the Gemini API and returns the response.
        API key is fetched and configured here for each call.

        Args:
            conversation_history: A list of message dictionaries, 
                                  e.g., [{"role": "user", "parts": [{"text": "Hello"}]}]

        Returns:
            The model's text response.

        Raises:
            Exception if the API call fails or returns an error.
        """
        try:
            # Fetch and configure API key for this call
            gemini_api_key = get_api_key_from_secrets()
            if not gemini_api_key:
                error_msg = ("Gemini API key is not configured or could not be loaded. "
                             "Please ensure it is set correctly in the secrets manager.")
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Log the key being used (from previous debugging, can be removed if too verbose later)
            self.logger.info(f"GeminiClient attempting to use API Key: {gemini_api_key[:4]}...{gemini_api_key[-4:] if len(gemini_api_key) > 8 else ''}") # Log partial key
            genai.configure(api_key=gemini_api_key)

            self.logger.info(f"Sending conversation to Gemini model: {self.model.model_name}")
            # The conversation_history is already in the correct format for model.generate_content
            response = await self.model.generate_content_async(conversation_history) # Use async version
            
            full_response_text = "".join(part.text for part in response.parts) if response.parts else ""

            if not full_response_text and response.prompt_feedback:
                self.logger.error(f"Gemini API call failed due to prompt feedback: {response.prompt_feedback}")
                raise Exception(f"Gemini API call failed due to prompt feedback: {response.prompt_feedback}")
            
            self.logger.info("Successfully received response from Gemini.")
            return full_response_text

        except Exception as e:
            self.logger.error(f"An error occurred while calling the Gemini API: {e}", exc_info=True)
            # Re-raise the exception to be handled by the caller in ai_service
            raise Exception(f"An error occurred while calling the Gemini API: {e}")

if __name__ == '__main__':
    # Example usage (updated for the class):
    print("Testing Gemini Client Class...")
    
    # Configure a basic logger for the test
    test_logger = logging.getLogger("GeminiClientTest")
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    test_logger.addHandler(handler)

    api_key = get_api_key_from_secrets()
    if not api_key:
        test_logger.warning("GEMINI_API_KEY is not set. Skipping live API test.")
        test_logger.info("Please set your API key using: python scripts/secrets_manager.py --setup")
        try:
            test_logger.info("\nAttempting to initialize client with no configured key:")
            client = GeminiClient(logger=test_logger) # This should raise ValueError
        except ValueError as ve:
            test_logger.info(f"SUCCESS: Correctly caught API key not configured: {ve}")
        except Exception as ex:
            test_logger.error(f"UNEXPECTED error during initialization with bad key: {ex}", exc_info=True)

    else:
        test_logger.info("GEMINI_API_KEY is configured. Proceeding with live test.")
        try:
            client = GeminiClient(logger=test_logger)
            
            async def run_test():
                test_conversation = [
                    {"role": "user", "parts": [{"text": "Explain what a large language model is in one sentence."}]}
                ]
                test_logger.info(f"Sending conversation: {test_conversation}")
                
                response_text = await client.send_prompt_async(test_conversation)
                test_logger.info(f"SUCCESS: Gemini Response: {response_text}")

                test_logger.info("\nTesting with an empty user part (should ideally be handled by API or raise error):")
                # Note: The Gemini API might handle this gracefully or return specific feedback.
                # This test case demonstrates sending a potentially problematic prompt.
                empty_part_conversation = [
                    {"role": "user", "parts": [{"text": ""}]}
                ]
                try:
                    response_empty = await client.send_prompt_async(empty_part_conversation)
                    test_logger.info(f"Gemini Response (empty part): {response_empty}")
                except Exception as e_empty:
                    test_logger.warning(f"Caught error for empty part prompt (this might be expected): {e_empty}")

            import asyncio
            asyncio.run(run_test())

        except Exception as e:
            test_logger.error(f"An error occurred during GeminiClient test: {e}", exc_info=True) 