import requests
from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv()

# Access the environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")


def create_chat_completion(messages):
    """
    Function to create a chat completion using OpenAI's API.

    :param messages: A list of message dictionaries containing role and content.
    :return: The response from the OpenAI API as a dictionary.
    """
    url = "https://api.openai.com/v1/chat/completions"
    api_key = openai_api_key

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    data = {"model": "gpt-4", "messages": messages}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raises an error for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating chat completion: {e}")
        return {"error": "An error occurred while creating chat completion."}


api_tool = {
    "function": create_chat_completion,
    "definition": {
        "name": "create_chat_completion",
        "description": "Create a chat completion using OpenAI's API.",
        "parameters": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {
                                "type": "string",
                                "enum": ["system", "user", "assistant"],
                                "description": "The role of the message sender.",
                            },
                            "content": {
                                "type": "string",
                                "description": "The content of the message.",
                            },
                        },
                        "required": ["role", "content"],
                    },
                    "description": "A list of messages for the chat.",
                }
            },
            "required": ["messages"],
        },
    },
}

# If this script is imported as a module, we expose `api_tool`
__all__ = ["api_tool"]
