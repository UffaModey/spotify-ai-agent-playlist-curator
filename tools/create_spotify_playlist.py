import requests


def create_playlist(user_id, playlist_name, spotify_token):
    """
    Function to create a new playlist on Spotify.

    :param user_id: The Spotify user ID for whom the playlist will be created.
    :param playlist_name: The name of the new playlist to be created.
    :return: The response from the Spotify API as a dictionary.
    """
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    token = spotify_token

    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = {
        "name": playlist_name,
        "public": False,
        "description": "test description",
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raises an error for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating playlist: {e}")
        return {"error": "An error occurred while creating the playlist."}


api_tool = {
    "function": create_playlist,
    "definition": {
        "name": "create_playlist",
        "description": "Create a new playlist on Spotify.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The Spotify user ID for whom the playlist will be created.",
                },
                "playlist_name": {
                    "type": "string",
                    "description": "The name of the new playlist to be created.",
                },
            },
            "required": ["user_id", "playlist_name"],
        },
    },
}

# If this script is imported as a module, we expose `api_tool`
__all__ = ["api_tool"]
