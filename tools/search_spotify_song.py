import requests

def search_for_item(q, spotify_token, item_type="track"):
    """
    Function to search for items on Spotify.

    :param q: The search query for the item.
    :param item_type: The type of item to search for (default: "track,album").
    :return: The result of the search as a dictionary.
    """
    url = "https://api.spotify.com/v1/search"
    access_token = spotify_token

    headers = {"Authorization": f"Bearer {access_token}"}

    params = {"q": q, "type": item_type}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raises an error for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error searching for item: {e}")
        return {"error": "An error occurred while searching for the item."}


api_tool = {
    "function": search_for_item,
    "definition": {
        "name": "search_for_item",
        "description": "Search for items on Spotify.",
        "parameters": {
            "type": "object",
            "properties": {
                "q": {
                    "type": "string",
                    "description": "The search query for the item.",
                },
                "item_type": {
                    "type": "string",
                    "description": "The type of item to search for.",
                },
            },
            "required": ["q"],
        },
    },
}

# If this script is imported as a module, we expose `api_tool`
__all__ = ["api_tool"]
