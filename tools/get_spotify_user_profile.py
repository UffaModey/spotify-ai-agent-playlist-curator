import requests


def get_current_user_profile(spotify_token):
    """
    Function to get the current user's profile from Spotify.

    :return: The current user's profile information as a dictionary.
    """
    url = "https://api.spotify.com/v1/me"
    bearer_token = spotify_token

    headers = {"Authorization": f"Bearer {bearer_token}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an error for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting user profile: {e}")
        return {"error": "An error occurred while getting the user profile."}


api_tool = {
    "function": get_current_user_profile,
    "definition": {
        "name": "get_current_user_profile",
        "description": "Retrieve the current user's profile from Spotify.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

# If this script is imported as a module, we expose `api_tool`
__all__ = ["api_tool"]
