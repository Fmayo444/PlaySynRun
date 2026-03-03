from flask import Flask, request, redirect, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import os

# --- CONFIGURATION ---
CLIENT_ID = '9197d25ded914014804b080f47319c9a'       # Paste from Spotify Developer Dashboard
CLIENT_SECRET = 'a24bda600b2544c8bdd71b8f87ddd76d' # Paste from Spotify Developer Dashboard
REDIRECT_URI = 'http://localhost:8888/callback'
TARGET_DURATION_MIN = 25
TOLERANCE_SEC = 30 # Allow playlist to be +/- 30 seconds of target
MIN_BPM = 155      # Minimum tempo for a 5k run
MIN_ENERGY = 0.6   # 0.0 to 1.0 (1.0 is highest energy)

# Convert target to milliseconds for Spotify API
target_ms = TARGET_DURATION_MIN * 60 * 1000
tolerance_ms = TOLERANCE_SEC * 1000

# --- AUTHENTICATION ---
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope="playlist-modify-public user-top-read"
))

def create_running_mix():
    print("--- 🎧 Scanning your top tracks for running gems... ---")
    
    # 1. Get User's Top Tracks (Fetching 50 to ensure we have enough candidates)
    results = sp.current_user_top_tracks(limit=50, time_range='medium_term')
    candidates = []

    # 2. Filter for BPM and Energy
    # We must fetch audio features in batches to be efficient
    track_ids = [item['id'] for item in results['items']]
    audio_features = sp.audio_features(track_ids)

    for i, features in enumerate(audio_features):
        if not features: continue
        
        # Check against our Running Criteria
        if (features['tempo'] >= MIN_BPM and features['energy'] >= MIN_ENERGY):
            candidates.append({
                'id': results['items'][i]['id'],
                'name': results['items'][i]['name'],
                'duration': features['duration_ms']
            })

    print(f"Found {len(candidates)} candidates matching BPM > {MIN_BPM}.")

    # 3. The Optimization Logic (Randomized Greedy Approach)
    # Shuffle so you get a different mix every time you run the script
    random.shuffle(candidates)
    
    final_playlist = []
    current_duration = 0
    
    print("--- 🏃 Building the 25-minute curve... ---")
    
    for track in candidates:
        # Check if adding this track keeps us under the limit + tolerance
        if current_duration + track['duration'] <= target_ms + tolerance_ms:
            final_playlist.append(track['id'])
            current_duration += track['duration']
            print(f"Added: {track['name']} ({track['duration']//1000}s)")
            
            # Optimization: If we are within the "perfect" window (target +/- tolerance), STOP.
            if abs(current_duration - target_ms) <= tolerance_ms:
                break
    
    # Check if we failed to fill the time
    total_min = current_duration / 60000
    print(f"Total Duration: {total_min:.2f} minutes")

    if total_min < (TARGET_DURATION_MIN - 1):
        print("⚠️ Warning: Not enough high-BPM songs in your Top 50 to fill 25 mins.")
        print("Try increasing the 'limit' in sp.current_user_top_tracks or lowering BPM threshold.")
        return

    # 4. Create the Playlist on Spotify
    user_id = sp.current_user()['id']
    playlist = sp.user_playlist_create(user_id, f"My {TARGET_DURATION_MIN} Min 5k Mix", public=True)
    
    sp.playlist_add_items(playlist['id'], final_playlist)
    print(f"✅ Success! Playlist created: {playlist['external_urls']['spotify']}")

if __name__ == "__main__":
    create_running_mix()