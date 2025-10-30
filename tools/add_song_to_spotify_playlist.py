import requests
import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Access the environment variables
# spotify_token = os.getenv("SPOTIFY_BEARER_TOKEN")


def add_items_to_playlist(playlist_id, uris, spotify_token):
    """
    Function to add one or more items to a user's Spotify playlist.

    :param playlist_id: The ID of the playlist to which items will be added.
    :param uris: A list of Spotify track or episode URIs to be added to the playlist.
    :return: The response from the Spotify API as a dictionary.
    """
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    token = spotify_token

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    data = {"uris": uris}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raises an error for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error adding items to playlist: {e}")
        return {"error": "An error occurred while adding items to the playlist."}


api_tool = {
    "function": add_items_to_playlist,
    "definition": {
        "name": "add_items_to_playlist",
        "description": "Add one or more items to a user's Spotify playlist.",
        "parameters": {
            "type": "object",
            "properties": {
                "playlist_id": {
                    "type": "string",
                    "description": "The ID of the playlist to which items will be added.",
                },
                "uris": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "A list of Spotify track or episode URIs to be added to the playlist.",
                },
            },
            "required": ["playlist_id", "uris"],
        },
    },
}

# If this script is imported as a module, we expose `api_tool`
__all__ = ["api_tool"]
