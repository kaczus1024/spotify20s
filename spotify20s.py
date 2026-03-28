import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import time
import random

# 1. KONFIGURACJA I SESJA
load_dotenv("spot.env")
st.set_page_config(page_title="Spotify Snippets Pro", page_icon="🎵", layout="wide")

# Inicjalizacja stanów sesji
if 'playing' not in st.session_state: st.session_state.playing = False
if 'track_index' not in st.session_state: st.session_state.track_index = 0
if 'tracks_queue' not in st.session_state: st.session_state.tracks_queue = []
if 'current_target_id' not in st.session_state: st.session_state.current_target_id = None

# 2. AUTORYZACJA (Wersja Poprawiona dla Chmury)
@st.cache_resource
def get_sp():
    auth_manager = SpotifyOAuth(
        client_id=st.secrets["SPOTIPY_CLIENT_ID"],
        client_secret=st.secrets["SPOTIPY_CLIENT_SECRET"],
        redirect_uri=st.secrets["SPOTIPY_REDIRECT_URI"],
        scope="user-modify-playback-state user-read-playback-state playlist-read-private playlist-read-collaborative user-library-read playlist-modify-public playlist-modify-private",
        open_browser=False,
        cache_path=".spotify_cache" # Ważne dla zachowania sesji w chmurze
    )
    
    # Sprawdzamy, czy mamy już token
    token_info = auth_manager.get_cached_token()
    
    if not token_info:
        # Pobieramy URL do autoryzacji
        auth_url = auth_manager.get_authorize_url()
        st.link_button("🔐 Zaloguj się do Spotify", auth_url)
        
        # Sprawdzamy, czy wróciliśmy z kodem w adresie URL
        query_params = st.query_params
        if "code" in query_params:
            auth_manager.get_access_token(query_params["code"])
            st.success("Autoryzacja pomyślna! Odśwież stronę.")
            st.rerun()
        else:
            st.info("Kliknij powyższy przycisk, aby połączyć aplikację z Twoim kontem Spotify.")
            st.stop() # Zatrzymuje resztę kodu do czasu logowania

    return spotipy.Spotify(auth_manager=auth_manager)

# 3. FUNKCJE POMOCNICZE
def clone_playlist(source_id):
    try:
        source_playlist = sp.playlist(source_id)
        tracks_res = sp.playlist_tracks(source_id)
        track_uris = [item['track']['uri'] for item in tracks_res['items'] if item['track']]
        new_name = f"Kopia: {source_playlist['name']}"
        new_pl = sp.user_playlist_create(user_id, new_name, public=False)
        for i in range(0, len(track_uris), 100):
            sp.playlist_add_items(new_pl['id'], track_uris[i:i+100])
        return new_pl['id'], new_name
    except Exception as e:
        st.error(f"Nie udało się sklonować listy: {e}")
        return None, None

@st.cache_data(ttl=3600)
def get_artist_genres(artist_id):
    try:
        artist = sp.artist(artist_id)
        return ", ".join(artist['genres']).capitalize()
    except: return "Nieznany"

# 4. INTERFEJS - URZĄDZENIE
st.title("🎵 Spotify Snippets Pro")
st.sidebar.header("⚙️ Ustawienia")

devices_res = sp.devices()
device_list = {d['name']: d['id'] for d in devices_res.get('devices', [])}

if not device_list:
    st.sidebar.error("Brak aktywnych urządzeń!")
    st.stop()

selected_device_name = st.sidebar.selectbox("Urządzenie:", list(device_list.keys()))
active_device_id = device_list[selected_device_name]

# 5. WYBÓR ŹRÓDŁA
st.subheader("📂 Wybierz playlistę")
source_option = st.radio("Źródło:", ["Moja biblioteka", "Wklej link"], horizontal=True)

target_id = None
if source_option == "Moja biblioteka":
    playlists = sp.current_user_playlists(limit=50)['items']
    pl_dict = {p['name']: p['id'] for p in playlists}
    sel_name = st.selectbox("Wybierz listę:", list(pl_dict.keys()))
    target_id = pl_dict[sel_name]
else:
    url_input = st.text_input("Wklej URL playlisty:")
    if url_input:
        target_id = url_input.split('/')[-1].split('?')[0]

# 6. KONTROLA ODTWARZANIA
st.divider()
do_shuffle = st.checkbox("🔀 Losowa kolejność", value=True)

col_prev, col_play, col_next, col_stop = st.columns([1, 1, 1, 1])

with col_play:
    if st.button("▶️ START / RESET", use_container_width=True):
        res = sp.playlist_tracks(target_id)['items']
        st.session_state.tracks_queue = [item.get('track') or item.get('item') for item in res if (item.get('track') or item.get('item'))]
        if do_shuffle: random.shuffle(st.session_state.tracks_queue)
        st.session_state.track_index = 0
        st.session_state.playing = True
        st.rerun()

with col_prev:
    if st.button("⏮️ POPRZEDNI", use_container_width=True, disabled=not st.session_state.playing):
        st.session_state.track_index = max(0, st.session_state.track_index - 1)
        st.rerun()

with col_next:
    if st.button("⏭️ NASTĘPNY", use_container_width=True, disabled=not st.session_state.playing):
        st.session_state.track_index += 1
        st.rerun()

with col_stop:
    if st.button("🛑 STOP", use_container_width=True):
        st.session_state.playing = False
        try: sp.pause_playback(device_id=active_device_id)
        except: pass
        st.rerun()

# 7. LOGIKA ODTWARZANIA
if st.session_state.playing and st.session_state.tracks_queue:
    idx = st.session_state.track_index
    
    if idx < len(st.session_state.tracks_queue):
        t = st.session_state.tracks_queue[idx]
        
        # Dane utworu
        artist_name = t['artists'][0]['name']
        artist_id = t['artists'][0]['id']
        album_name = t['album']['name']
        release_year = t['album']['release_date'][:4]
        genres = get_artist_genres(artist_id)

        # UI Karty
        container = st.container()
        col_img, col_info = container.columns([1, 3])
        with col_img:
            if t['album']['images']:
                st.image(t['album']['images'][0]['url'], width=250)
        with col_info:
            st.markdown(f"## {t['name']}")
            st.write(f"**Wykonawca:** {artist_name}")
            st.write(f"**Album:** {album_name} ({release_year})")
            st.write(f"**Gatunek:** {genres}")
            st.caption(f"Utwór {idx + 1} z {len(st.session_state.tracks_queue)}")
            
        track_progress = st.progress(0)

        # Start fragmentu
        try:
            sp.start_playback(device_id=active_device_id, uris=[t['uri']], position_ms=45000)
            
            # Pętla snippetu (20 sek)
            for s in range(20):
                # Sprawdzenie czy w międzyczasie nie kliknięto Stop lub Następny
                # (W Streamlit kliknięcie przycisku przerywa ten skrypt i uruchamia go od nowa)
                time.sleep(1)
                track_progress.progress((s + 1) / 20, text=f"Słuchasz fragmentu: {s+1}s / 20s")
            
            # Po zakończeniu snippetu - idź do następnego
            st.session_state.track_index += 1
            st.rerun()
            
        except Exception as e:
            st.error(f"Błąd odtwarzania: {e}")
            st.session_state.track_index += 1
            st.rerun()
    else:
        st.success("Koniec listy!")
        st.session_state.playing = False
