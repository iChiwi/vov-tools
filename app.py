import time
import math
import json
import os
import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import chardet
import google.generativeai as genai

app = Flask(__name__)

# --- Global variables ---
console_logs = []  # to store log messages
queue_data = []    # placeholder for queue info

# Default values (will be overwritten on login)
SPOTIPY_CLIENT_ID = None
SPOTIPY_CLIENT_SECRET = None
SPOTIPY_REDIRECT_URI = 'http://localhost:8888/callback'
LOG_FILE = "song-name.log"

# Use a generic relative file path for chat logs
CHATLOG_PATH = "YOUR_CHATLOG_PATH/chatlog.txt"

CHECK_INTERVAL = 1  # seconds when a song is playing
IDLE_INTERVAL = 5   # seconds when no song is playing

# Gemini API initialization
GEMINI_MODEL = "gemini-2.0-flash"
genai.configure(api_key="YOUR_GEMINI_API_KEY")

# Global Spotify client variable
sp = None

# --- Utility function to add to console log ---
def new_log(message):
    entry = f"{message}"
    console_logs.append(entry)
    print(entry)

def format_time(seconds):
    minutes = math.floor(seconds / 60)
    return f"{minutes} min"

def detect_file_encoding(file_path):
    with open(file_path, "rb") as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def read_chatlog():
    try:
        encoding = detect_file_encoding(CHATLOG_PATH)
        new_log(f"Detected encoding: {encoding}")
        with open(CHATLOG_PATH, "r", encoding=encoding) as file:
            file.seek(0, os.SEEK_END)
            new_log("Opened chatlog file and moved to the end.")
            while True:
                line = file.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                if "[VOV]" in line and "[Request]" in line:
                    new_log(f"Detected request line: {line.strip()}")
                    yield line.strip()
    except Exception as e:
        new_log(f"Error reading chatlog: {e}")
        try:
            with open(CHATLOG_PATH, "r", encoding="latin-1") as file:
                file.seek(0, os.SEEK_END)
                new_log("Opened chatlog file with latin-1 encoding and moved to the end.")
                while True:
                    line = file.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    if "[VOV]" in line and "[Request]" in line:
                        new_log(f"Detected request line: {line.strip()}")
                        yield line.strip()
        except Exception as e2:
            new_log(f"Fallback encoding also failed: {e2}")

def update_song_log(last_minute):
    global sp
    try:
        current_track = sp.currently_playing()
        if current_track and current_track.get('is_playing'):
            track_name = current_track['item']['name']
            artist_name = current_track['item']['artists'][0]['name']
            progress_ms = current_track['progress_ms']
            duration_ms = current_track['item']['duration_ms']
            remaining_time = (duration_ms - progress_ms) / 1000
            current_minute = math.floor(remaining_time / 60)
            if current_minute != last_minute:
                time_left = format_time(remaining_time)
                log_entry = f"{{FFFFFF}}[{time_left}] {{4187a3}}{track_name} {{E65C00}}- {{4187a3}}{artist_name}{{E65C00}}"
                with open(LOG_FILE, "w") as file:
                    file.write(log_entry)
                new_log(f"Updated log: {log_entry.strip()}")
                return current_minute
            else:
                return last_minute
        else:
            new_log("No song is currently playing.")
            return None
    except Exception as e:
        new_log(f"Spotify API error in update_song_log: {e}")
        return None

def refine_song_request(song_name, artist_name):
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = (
            f"Fix this song request for a better Spotify search.\n\n"
            f"User input: '{song_name}' by '{artist_name or 'Unknown'}'.\n"
            f"- Correct any typos or unclear names.\n"
            f"- If the song name seems nonsensical, guess the closest real song.\n"
            f"- If no artist is given, assume the most likely popular one.\n"
            f"- If an artist was given, use the song from that artist. Don't use the most popular.\n"
            f"- Ensure correct spelling and formatting.\n"
            f"Return **ONLY JSON** like this: {{'song': 'fixed name', 'artist': 'correct artist'}}"
        )
        response = model.generate_content(prompt)
        if response and response.text:
            try:
                json_text = response.text.strip().replace("```json", "").replace("```", "").strip()
                result = json.loads(json_text)
                refined_song = result.get("song", song_name).strip() if result.get("song") else song_name
                refined_artist = result.get("artist", artist_name).strip() if result.get("artist") else artist_name
                if refined_artist and refined_artist.lower() in refined_song.lower():
                    refined_song = refined_song.replace(refined_artist, "").strip(" -")
                new_log(f"Refined Song Request: {refined_song} by {refined_artist or 'Unknown'}")
                return refined_song, refined_artist
            except json.JSONDecodeError:
                new_log("AI returned invalid JSON, using original song request.")
        else:
            new_log("AI response was empty, using original song request.")
    except Exception as e:
        new_log(f"Error refining song request: {e}")
    return song_name.strip(), artist_name.strip()

def is_troll_song(song_name, artist_name):
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = f"Is the song '{song_name}' by '{artist_name or 'Unknown'}' considered a troll or unserious song? Reply with 'yes' or 'no'. An example of a troll song is baby shark."
        response = model.generate_content(prompt)
        result = response.text.strip().lower()
        return result == "yes"
    except Exception as e:
        new_log(f"Error checking for troll song: {e}")
        return False

def search_spotify_song(song_name, artist_name):
    global sp
    try:
        query = f"track:{song_name} artist:{artist_name}" if artist_name else f"track:{song_name}"
        results = sp.search(q=query, type="track", limit=10)
        if results["tracks"]["items"]:
            for track in results["tracks"]["items"]:
                if "remaster" not in track["name"].lower():
                    return track["uri"]
            return results["tracks"]["items"][0]["uri"]
        return None
    except Exception as e:
        new_log(f"Error searching for song on Spotify: {e}")
        return None

def is_song_in_queue(song_uri):
    global sp
    try:
        current_queue = sp.queue()
        for track in current_queue.get('queue', []):
            if track['uri'] == song_uri:
                return True
        return False
    except Exception as e:
        new_log(f"Error checking queue: {e}")
        return False

def add_to_spotify_queue(song_uri):
    global sp
    try:
        if is_song_in_queue(song_uri):
            new_log(f"Song already in queue: {song_uri}")
            return
        sp.add_to_queue(song_uri)
        new_log(f"Added to queue: {song_uri}")
    except Exception as e:
        new_log(f"Error adding song to queue: {e}")

def process_requests():
    for request_line in read_chatlog():
        try:
            request_text = request_line.split("[Request]")[1].strip()
            parts = request_text.split(" - ", maxsplit=1)
            song_name = parts[0].strip()
            artist_name = parts[1].strip() if len(parts) > 1 else None
            new_log(f"Processing request: Song='{song_name}', Artist='{artist_name or 'Unknown'}'")
            refined_song_name, refined_artist_name = refine_song_request(song_name, artist_name)
            if is_troll_song(refined_song_name, refined_artist_name):
                new_log(f"Skipping troll song: {refined_song_name} by {refined_artist_name}")
                continue
            song_uri = search_spotify_song(refined_song_name, refined_artist_name)
            if song_uri:
                add_to_spotify_queue(song_uri)
            else:
                new_log(f"Refined song not found: {refined_song_name} by {refined_artist_name or 'Unknown'}")
                song_uri = search_spotify_song(song_name, artist_name)
                if song_uri:
                    add_to_spotify_queue(song_uri)
                else:
                    new_log(f"Original song not found: {song_name} by {artist_name or 'Unknown'}")
        except Exception as e:
            new_log(f"Error processing request: {e}")

def process_requests_thread():
    while True:
        process_requests()
        time.sleep(1)

def update_log_thread():
    last_minute = None
    while True:
        try:
            current_track = sp.currently_playing()
            if current_track and current_track.get('is_playing'):
                last_minute = update_song_log(last_minute)
                time.sleep(CHECK_INTERVAL)
            else:
                with open(LOG_FILE, "w") as file:
                    file.write("")
                new_log("No song is currently playing.")
                last_minute = None
                time.sleep(IDLE_INTERVAL)
        except Exception as e:
            new_log(f"Error occurred: {e}")
            time.sleep(IDLE_INTERVAL)

def start_background_threads():
    t1 = threading.Thread(target=process_requests_thread, daemon=True)
    t2 = threading.Thread(target=update_log_thread, daemon=True)
    t1.start()
    t2.start()

@app.route("/", methods=["GET"])
def index():
    if not session.get("logged_in"):
        return render_template("index.html", logged_in=False)
    else:
        global sp
        try:
            current_q = sp.queue().get("queue", []) if sp else []
        except Exception as e:
            current_q = []
            new_log(f"Error retrieving queue: {e}")
        try:
            token = sp.auth_manager.get_access_token(as_dict=False) if sp else ""
        except Exception as e:
            new_log(f"Error retrieving access token: {e}")
            token = ""
        return render_template(
            "index.html",
            logged_in=True,
            queue=current_q,
            spotify_token=token,
            redirect_uri=SPOTIPY_REDIRECT_URI
        )

@app.route("/login", methods=["POST"])
def login():
    global SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, sp
    SPOTIPY_CLIENT_ID = request.form.get("client_id")
    SPOTIPY_CLIENT_SECRET = request.form.get("client_secret")
    if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
        return redirect(url_for("index"))
    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="user-read-currently-playing user-read-playback-state user-modify-playback-state",
        cache_path=".spotify_cache",
        open_browser=True
    )
    sp = spotipy.Spotify(auth_manager=auth_manager, requests_timeout=20)
    session["logged_in"] = True
    new_log("User logged in and authenticated with Spotify.")
    start_background_threads()
    return redirect(url_for("index"))

@app.route("/logs", methods=["GET"])
def get_logs():
    logs = console_logs[-12:][::-1]
    return jsonify(logs)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    global sp
    sp = None
    new_log("User logged out.")
    return redirect(url_for("index"))

@app.route("/queue", methods=["GET"])
def get_queue():
    global sp
    if sp is None:
        new_log("Spotify client not initialized.")
        return jsonify([])
    try:
        current_q = sp.queue().get("queue", [])
    except Exception as e:
        current_q = []
        new_log(f"Error retrieving queue via API: {e}")
    return jsonify(current_q)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=False)
