import json
import logging
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from tools.open_ai_generate_songs import create_chat_completion
from tools.get_spotify_user_profile import get_current_user_profile
from tools.create_spotify_playlist import create_playlist
from tools.search_spotify_song import search_for_item
from tools.add_song_to_spotify_playlist import add_items_to_playlist

# -------------------------
# Setup
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("playlist_curator")

import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Access the environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")

SPOTIFY_ADD_BATCH_SIZE = 100  # Spotify API supports up to 100 URIs per add request
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SCOPE = os.getenv("SCOPE")

# Initialize Spotipy Auth Manager
auth_manager = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope=SCOPE,
)

# Session state
if "token_info" not in st.session_state:
    st.session_state.token_info = None


@dataclass
class Song:
    title: str
    artist: str

    def to_query(self) -> str:
        return f"{self.title} {self.artist}".strip()

    def __str__(self) -> str:
        return f"{self.title} — {self.artist}"


# -------------------------
# Helpers
# -------------------------
def safe_call(tool_name: str, func, *args, **kwargs) -> Dict[str, Any]:
    """
    Call a tool and return a dict with either {"result": ...} or {"error": {"tool": tool_name, "exception": exc_str}}.
    This keeps tool errors explicit and traceable.
    """
    try:
        result = func(*args, **kwargs)
        return {"result": result}
    except Exception as exc:
        tb = traceback.format_exc()
        logger.exception("Tool %s raised an exception", tool_name)
        return {"error": {"tool": tool_name, "exception": str(exc), "traceback": tb}}


def parse_openai_song_list(raw_content: str, limit: int) -> List[Song]:
    """
    Parse the OpenAI completion content into a list of Song dataclasses.
    Expecting a JSON array of objects with `title` and `artist`.
    """
    try:
        parsed = json.loads(raw_content)
        if not isinstance(parsed, list):
            raise ValueError("OpenAI response JSON is not a list.")
        songs: List[Song] = []
        for i, item in enumerate(parsed[:limit]):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict item at index %s: %s", i, item)
                continue
            title = item.get("title") or item.get("name") or item.get("track")
            artist = item.get("artist") or item.get("artists")
            if not title or not artist:
                logger.warning("Skipping item missing title/artist: %s", item)
                continue
            songs.append(Song(title=str(title).strip(), artist=str(artist).strip()))
        return songs
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to decode JSON from OpenAI response: {exc}")


def extract_first_track_uri(track_search_response: Dict[str, Any]) -> Optional[str]:
    """Given Spotify search response JSON, extract the first track.uri or None."""
    if not track_search_response:
        return None
    tracks = track_search_response.get("tracks")
    if not tracks:
        return None
    items = tracks.get("items", [])
    if not items:
        return None
    first = items[0]
    return first.get("uri")


def chunked(iterable: List[Any], size: int):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="AI Spotify Playlist Curator", page_icon="🎵")

if "playlist_info" not in st.session_state:
    st.session_state.playlist_info = {}
if "errors" not in st.session_state:
    st.session_state.errors = []

st.title("🎵 AI Spotify Playlist Curator")

if not st.session_state.token_info:
    auth_url = auth_manager.get_authorize_url()
    st.markdown(f"[🔑 Login with Spotify]({auth_url})", unsafe_allow_html=True)

    # Handle redirect from Spotify with ?code=
    query_params = st.query_params.to_dict()
    if "code" in query_params:
        code = query_params["code"]
        token_info = auth_manager.get_access_token(code, as_dict=True)
        st.session_state.token_info = token_info
        st.success("Successfully logged in with Spotify! 🎉")
        st.rerun()
else:
    # Refresh token if expired
    if auth_manager.is_token_expired(st.session_state.token_info):
        st.session_state.token_info = auth_manager.refresh_access_token(
            st.session_state.token_info["refresh_token"]
        )

    sp = spotipy.Spotify(auth=st.session_state.token_info["access_token"])
    profile = sp.current_user()
    st.success(f"Logged in as: {profile['display_name']}")

    playlist_description = st.text_area(
        "Describe the playlist you want to generate (e.g., songs about summer love)"
    )
    limit = st.number_input(
        "How many songs should be in the playlist?", min_value=1, max_value=50, value=10
    )

    if st.button("Generate Playlist"):
        st.session_state.errors = []  # reset per-run
        # Input validation
        if not playlist_description or not limit:
            st.warning("Please provide playlist description and limit.")
        else:
            st.info("Generating playlist...")

            # -------------------------
            # Tool 1: OpenAI - generate songs
            # -------------------------
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an AI music assistant that transforms a user's idea, mood, or theme "
                        "into a curated Spotify playlist. You must respond with a JSON object that "
                        "contains a short and catchy playlist title and a list of real songs likely to exist on Spotify."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate a playlist based on the following description: '{playlist_description}'.\n\n"
                        "Return a JSON object with this format:\n\n"
                        "{\n"
                        '  "playlist_title": "string",\n'
                        '  "songs": [\n'
                        f'    {{ "title": "string", "artist": "string" }}, ... up to {limit} songs\n'
                        "  ]\n"
                        "}\n\n"
                        "Make sure the playlist_title is engaging, under 6 words, and fits the theme. "
                    ),
                },
            ]

            openai_call = safe_call(
                "OpenAI (create_chat_completion)", create_chat_completion, messages
            )
            if "error" in openai_call:
                err = openai_call["error"]
                st.error(f"OpenAI tool error: {err['tool']}: {err['exception']}")
                st.text(err.get("traceback", ""))
                st.session_state.errors.append(err)
                song_objects: List[Song] = []
            else:
                try:
                    content = openai_call["result"]["choices"][0]["message"]["content"]
                    parsed = json.loads(content)

                    playlist_title = parsed.get(
                        "playlist_title", f"AI: {playlist_description[:40]}"
                    )
                    songs_data = parsed.get("songs", [])
                    song_objects = [
                        Song(title=s["title"], artist=s["artist"])
                        for s in songs_data
                        if "title" in s and "artist" in s
                    ]

                except json.JSONDecodeError as exc:
                    st.error(f"Failed to decode JSON from OpenAI response: {exc}")
                    playlist_title = f"AI: {playlist_description[:40]}"
                    song_objects = []

                # -------------------------
                # Tool 2: Spotify - get current user profile
                # -------------------------
                profile_call = safe_call(
                    "Spotify (get_current_user_profile)", get_current_user_profile
                )
                if "error" in profile_call:
                    err = profile_call["error"]
                    st.error(
                        f"Spotify user profile error: {err['tool']}: {err['exception']}"
                    )
                    st.text(err.get("traceback", ""))
                    st.session_state.errors.append(err)
                    st.stop()
                user_profile = profile_call["result"]
                user_id = user_profile.get("id")
                if not user_id:
                    st.error(
                        "Could not retrieve Spotify user ID. Check your token / auth flow."
                    )
                    st.stop()
                st.success(f"Successfully validated Spotify credentials")

                # -------------------------
                # Tool 3: Create playlist
                # -------------------------
                playlist_name = f"AI: {playlist_title[:40]}"
                create_playlist_call = safe_call(
                    "Spotify (create_playlist)", create_playlist, user_id, playlist_name
                )
                if "error" in create_playlist_call:
                    err = create_playlist_call["error"]
                    st.error(
                        f"Create playlist error: {err['tool']}: {err['exception']}"
                    )
                    st.text(err.get("traceback", ""))
                    st.session_state.errors.append(err)
                    st.stop()
                playlist_response = create_playlist_call["result"]
                playlist_id = playlist_response.get("id")
                if not playlist_id:
                    st.error("Failed to create playlist (no id returned).")
                    st.session_state.errors.append(
                        {
                            "tool": "create_playlist",
                            "exception": "no playlist id returned",
                        }
                    )
                    st.stop()
                st.success(f"Created playlist: {playlist_name}")

                # -------------------------
                # Tool 4: Search for each song -> get URIs
                # -------------------------
                track_uris: List[str] = []
                for s in song_objects:
                    q = f"track:{s.title} artist:{s.artist}"
                    search_call = safe_call(
                        "Spotify (search_for_item)", search_for_item, q
                    )
                    if "error" in search_call:
                        err = search_call["error"]
                        st.error(
                            f"Search error for '{s}': {err['tool']}: {err['exception']}"
                        )
                        st.session_state.errors.append({"song": str(s), **err})
                        continue
                    track_data = search_call["result"]
                    uri = extract_first_track_uri(track_data)
                    if uri:
                        track_uris.append(uri)
                    else:
                        st.warning(f"No track found on Spotify for: {s}")
                        st.session_state.errors.append(
                            {
                                "song": str(s),
                                "tool": "search_for_item",
                                "exception": "no track uri found",
                            }
                        )

                st.info(
                    f"{len(track_uris)} track URIs resolved out of {len(song_objects)} requested."
                )

                # -------------------------
                # Tool 5: Add tracks in batches
                # -------------------------
                if track_uris:
                    try:
                        # chunk and call the provided helper (which may itself call Spotify)
                        for chunk in chunked(track_uris, SPOTIFY_ADD_BATCH_SIZE):
                            add_call = safe_call(
                                "Spotify (add_items_to_playlist)",
                                add_items_to_playlist,
                                playlist_id,
                                chunk,
                            )
                            if "error" in add_call:
                                err = add_call["error"]
                                st.error(
                                    f"Failed to add tracks to playlist: {err['tool']}: {err['exception']}"
                                )
                                st.text(err.get("traceback", ""))
                                st.session_state.errors.append(err)
                                # decide whether to continue trying remaining chunks or stop; here we continue
                                continue
                        st.success("Tracks added to playlist (where possible).")
                    except Exception as exc:
                        tb = traceback.format_exc()
                        st.error(f"Unexpected error while adding tracks: {exc}")
                        st.text(tb)
                        logger.exception("Unexpected error adding tracks")
                        st.session_state.errors.append(
                            {
                                "tool": "add_items_to_playlist_unexpected",
                                "exception": str(exc),
                                "traceback": tb,
                            }
                        )
                else:
                    st.warning("No track URIs to add to playlist.")

                # -------------------------
                # Persist results to session state and show final summary
                # -------------------------
                st.session_state.playlist_info = {
                    "playlist_name": playlist_name,
                    "playlist_description": playlist_description,
                    "songs": [
                        {"title": s.title, "artist": s.artist} for s in song_objects
                    ],
                    "resolved_track_count": len(track_uris),
                    "playlist_id": playlist_id,
                }

    # Always display the last generated playlist info (if any)
    if st.session_state.playlist_info:
        info = st.session_state.playlist_info
        st.subheader("Generated Playlist")
        st.write(f"**Name:** {info.get('playlist_name')}")
        st.write(f"**Description used:** {info.get('playlist_description')}")
        st.write(
            f"**Resolved tracks added (approx):** {info.get('resolved_track_count')}"
        )
        st.write("**Songs returned by OpenAI:**")
        for s in info.get("songs", []):
            st.write(f"- {s['title']} — {s['artist']}")

    # Show collected errors (if any)
    if st.session_state.errors:
        st.subheader("Errors / Warnings")
        for e in st.session_state.errors:
            st.json(e)
