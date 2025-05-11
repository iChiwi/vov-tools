import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import math

# Define credentials (Replace with your actual values)
SPOTIPY_CLIENT_ID = "YOUR_CLIENT_ID"
SPOTIPY_CLIENT_SECRET = "YOUR_CLIENT_SECRET"
SPOTIPY_REDIRECT_URI = "http://localhost:8888/callback"

LOG_FILE = "song-name.log"

CHECK_INTERVAL = 1  # seconds when a song is playing
IDLE_INTERVAL = 5   # seconds when no song is playing

# Initialize Spotify client
try:
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="user-read-playback-state"
    ))
except Exception as e:
    print(f"Error initializing Spotify client: {e}")
    exit(1)

def format_time(seconds):
    minutes = math.floor(seconds / 60)
    return f"{minutes} min"

def update_song_log(last_minute):
    global sp
    try:
        current_track = sp.currently_playing()
    except Exception as e:
        print(f"Error fetching track: {e}")
        return last_minute
    
    if current_track and current_track.get("is_playing") and current_track.get("item"):
        track_name = current_track["item"]["name"]
        artist_name = current_track["item"]["artists"][0]["name"]
        progress_ms = current_track["progress_ms"]
        duration_ms = current_track["item"]["duration_ms"]

        if progress_ms is None or duration_ms is None:
            return last_minute  # Avoid division by None

        remaining_time = (duration_ms - progress_ms) / 1000
        current_minute = math.floor(remaining_time / 60)

        if current_minute != last_minute:
            time_left = format_time(remaining_time)
            log_entry = f"{{FFFFFF}}[{time_left}] {{4187a3}}{track_name} {{E65C00}}- {{4187a3}}{artist_name}{{E65C00}}"
            
            try:
                with open(LOG_FILE, "w") as file:
                    file.write(log_entry)
            except Exception as e:
                print(f"Error writing to log file: {e}")

            return current_minute
    
    return last_minute

if __name__ == "__main__":
    last_minute = -1
    while True:
        last_minute = update_song_log(last_minute)
        time.sleep(CHECK_INTERVAL if last_minute != -1 else IDLE_INTERVAL)
