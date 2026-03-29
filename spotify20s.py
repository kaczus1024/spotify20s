import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import random

# 1. KONFIGURACJA STRONY
st.set_page_config(page_title="Spotify Snippets Pro", page_icon="🎵", layout="wide")

# Inicjalizacja stanów sesji
if 'playing' not in st.session_state: st.session_state.playing = False
if 'track_index' not in st.session_state: st.session_state.track_index = 0
if 'tracks_queue' not in st.session_state: st.session_state.tracks_queue = []

# 2. FUNKCJA AUTORYZACJI (NAPRAWIONA DLA SMARTFONA)
@st.cache_resource
def get_sp():
    # Pobieranie danych z Secrets
    client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="user-modify-playback-state user-read-playback-state playlist-read-private user-library-read",
        open_browser=False,
        cache_path=".spotify_cache"
    )

    # KROK A: Sprawdź czy w URL jest parametr 'code' (powrót ze Spotify)
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        try:
            auth_manager.get_access_token(code)
            # Czyścimy URL, żeby nie zapętlać logowania
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Błąd wymiany kodu: {e}")

    # KROK B: Sprawdź czy mamy ważny token w pamięci
    token_info = auth_manager.get_cached_token()

    if not token_info:
        auth_url = auth_manager.get_authorize_url()
        st.title("🔐 Logowanie Spotify")
        st.write("Kliknij przycisk poniżej, aby połączyć się ze Spotify:")
        st.link_button("Zaloguj się do Spotify", auth_url)
        st.stop() # Zatrzymuje skrypt do czasu powrotu z kodem
    
    return spotipy.Spotify(auth_manager=auth_manager)

# 3. POMOCNICZE
@st.cache_data(ttl=3600)
def get_artist_genres(_sp, artist_id):
    try:
        artist = _sp.artist(artist_id)
        return ", ".join(artist['genres']).capitalize()
    except: return "Brak"

# 4. START APLIKACJI
sp = get_sp()

if sp:
    try:
        user_name = sp.me()['display_name']
        st.success(f"Zalogowano jako: {user_name}")
        
        # --- RESZTA TWOJEGO KODU (URZĄDZENIA, PLAYLISTY) ---
        devices_res = sp.devices()
        device_list = {d['name']: d['id'] for d in devices_res.get('devices', [])}

        if not device_list:
            st.warning("Otwórz Spotify na telefonie, aby urządzenie było widoczne.")
            if st.button("Odśwież"): st.rerun()
            st.stop()

        selected_device = st.sidebar.selectbox("Urządzenie:", list(device_list.keys()))
        active_id = device_list[selected_device]

        # Wybór źródła
        source = st.radio("Źródło:", ["Biblioteka", "URL"], horizontal=True)
        target_id = None
        if source == "Biblioteka":
            pl = sp.current_user_playlists(limit=20)['items']
            sel = st.selectbox("Lista:", [p['name'] for p in pl])
            target_id = next(p['id'] for p in pl if p['name'] == sel)
        else:
            url = st.text_input("Link do listy:")
            if url: target_id = url.split('/')[-1].split('?')[0]

        # Sterowanie
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("▶️ START"):
            res = sp.playlist_tracks(target_id)['items']
            st.session_state.tracks_queue = [i['track'] for i in res if i['track']]
            random.shuffle(st.session_state.tracks_queue)
            st.session_state.track_index = 0
            st.session_state.playing = True
            st.rerun()
        
        if c2.button("⏮️"):
            st.session_state.track_index = max(0, st.session_state.track_index - 1)
            st.rerun()
        if c3.button("⏭️"):
            st.session_state.track_index += 1
            st.rerun()
        if c4.button("🛑"):
            st.session_state.playing = False
            sp.pause_playback(device_id=active_id)
            st.rerun()

        # Odtwarzanie
        if st.session_state.playing and st.session_state.tracks_queue:
            idx = st.session_state.track_index
            if idx < len(st.session_state.tracks_queue):
                t = st.session_state.tracks_queue[idx]
                st.image(t['album']['images'][0]['url'], width=300)
                st.subheader(f"{t['name']} - {t['artists'][0]['name']}")
                
                prog = st.progress(0)
                sp.start_playback(device_id=active_id, uris=[t['uri']], position_ms=45000)
                for s in range(20):
                    if not st.session_state.playing: break
                    time.sleep(1)
                    prog.progress((s+1)/20)
                
                if st.session_state.playing:
                    st.session_state.track_index += 1
                    st.rerun()
    except Exception as e:
        st.error(f"Błąd: {e}")
