import libsonic
import os
import pylast
import re
import time
import webbrowser

LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")
LASTFM_API_SECRET = os.environ.get("LASTFM_API_SECRET")
LASTFM_USERNAME = os.environ.get("LASTFM_USERNAME")
LASTFM_SESSION_KEY = os.environ.get("LASTFM_SESSION_KEY") # optional
SUBSONIC_URL = os.environ.get("SUBSONIC_URL")
SUBSONIC_USERNAME = os.environ.get("SUBSONIC_USERNAME")
SUBSONIC_PASSWORD = os.environ.get("SUBSONIC_PASSWORD")

def make_song_id(artist, title):
    """
    FIXME:
    Causes issues with songs that have (...) in the track name

    Edge case one:
    Last.fm: Ellie Goulding - Lights
    Subsonic: Ellie Goulding - Lights (Single Version)

    So I decided to remove the (...) from the track name which creates an edge case with remixed
    songs in starred list and a race condition that means the most recently starred gets loved.

    Edge case two:
    Weezer - Feels Like Summer
    Weezer - Feels Like Summer (Acoustic)

    Both ID to: weezer-feelslikesummer

    Last.fm only gets the first version:
    Weezer - Feels Like Summer
    OR
    Weezer - Feels Like Summer (Acoustic)
    but not both.
    """

    artist = re.sub(r'^(the|el|la|los|las|le|les)\s+', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'[^a-z]+', '', artist, flags=re.IGNORECASE)
    artist = artist.lower()

    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'[^a-z]+', '', title, flags=re.IGNORECASE)
    title = title.lower().strip()

    return f"{artist}-{title}"

# get starred list from Subsonic
print("Connecting to Subsonic...")

subsonic = libsonic.Connection(
    SUBSONIC_URL,
    SUBSONIC_USERNAME,
    SUBSONIC_PASSWORD,
    apiVersion="1.15.0",
    legacyAuth=True,
)

print("Getting starred songs from Subsonic...")

starred_songs = [
    {
        "artist": song.get("artist"),
        "title": song.get("title"), 
        "id": make_song_id(song.get("artist"), song.get("title")),
    } for song in subsonic.getStarred().get("starred").get("song")
]

print("Got", len(starred_songs), "song(s).")

# sign in and authenticate to Last.fm
print("Connecting to Last.fm...")

SESSION_KEY_FILE = os.path.join(os.path.expanduser("~"), ".session_key")
lastfm = pylast.LastFMNetwork(LASTFM_API_KEY, LASTFM_API_SECRET)
if not os.path.exists(SESSION_KEY_FILE) and not LASTFM_SESSION_KEY:
    skg = pylast.SessionKeyGenerator(lastfm)
    url = skg.get_web_auth_url()

    print(f"Please authorize this script to access your account: {url}\n")
    webbrowser.open(url)

    while True:
        try:
            LASTFM_SESSION_KEY = skg.get_web_auth_session_key(url)
            with open(SESSION_KEY_FILE, "w") as f:
                f.write(LASTFM_SESSION_KEY)
            break
        except pylast.WSError:
            time.sleep(1)
else:
    LASTFM_SESSION_KEY = open(SESSION_KEY_FILE).read()

lastfm.session_key = LASTFM_SESSION_KEY

# get loved sonds from Last.fm
print("Getting loved songs from Last.fm...")

loved_songs = [
    {
        "artist": song.track.get_artist().get_name(),
        "title": song.track.get_title(),
        "id": make_song_id(song.track.get_artist().get_name(), song.track.get_title()),
    } for song in lastfm.get_user(LASTFM_USERNAME).get_loved_tracks(None)
]

print("Got", len(loved_songs), "song(s).")

# get song deltas
print("Calculating deltas...")

missing_songs = [song for song in starred_songs if song['id'] not in [other_song['id'] for other_song in loved_songs]]
extra_songs = [song for song in loved_songs if song['id'] not in [other_song['id'] for other_song in starred_songs]]

print("Found", len(missing_songs), "missing song(s) and", len(extra_songs), "extra song(s).")

# update Last.fm
print("Removing extra songs:")
for song in extra_songs:
    print("Removing '" + song["artist"], "-", song["title"] + "' (" + song["id"] + ") from Last.fm loved list.")
    lastfm.get_track(song["artist"], song["title"]).unlove()
    time.sleep(1)

print("Adding missing songs:")
for song in missing_songs:
    print("Adding '" + song["artist"], "-", song["title"] + "' (" + song["id"] + ") to Last.fm loved list.")
    lastfm.get_track(song["artist"], song["title"]).love()
    time.sleep(1)