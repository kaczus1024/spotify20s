import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import random

# 1. KONFIGURACJA STRONY I SESJI
st.set_page_config(
    page_title="Spotify - przegląd utworów", 
    page_icon="🎵", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

if 'playing' not in st.session_state: st.session_state.playing = False
if 'track_index' not in st.session_state: st.session_state.track_index = 0
if 'tracks_queue' not in st.session_state: st.session_state.tracks_queue = []
if 'shuffle_mode' not in st.session_state: st.session_state.shuffle_mode = True

# 2. FUNKCJA AUTORYZACJI
@st.cache_resource
def get_sp():
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]
    except:
        st.error("Błąd: Brak kluczy w Streamlit Secrets!")
        st.stop()

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="user-modify-playback-state user-read-playback-state playlist-read-private user-library-read",
        open_browser=False,
        cache_path=".spotify_cache"
    )

    query_params = st.query_params
    if "code" in query_params:
        auth_manager.get_access_token(query_params["code"])
        st.query_params.clear()
        st.rerun()

    token_info = auth_manager.get_cached_token()
    if not token_info:
        auth_url = auth_manager.get_authorize_url()
        st.title("🔐 Logowanie Spotify")
        st.link_button("Zaloguj się do Spotify", auth_url)
        st.stop()
    
    return spotipy.Spotify(auth_manager=auth_manager)

# 3. FUNKCJE POMOCNICZE
@st.cache_data(ttl=3600)
def get_artist_genres(_sp, artist_id):
    try:
        artist = _sp.artist(artist_id)
        return ", ".join(artist['genres']).capitalize()
    except: return "Nieznany"

# Funkcja do pobierania WSZYSTKICH utworów z playlisty (omija limit 50)
def get_all_playlist_tracks(_sp, playlist_id):
    results = _sp.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = _sp.next(results)
        tracks.extend(results['items'])
    return tracks

# 4. START APLIKACJI
sp = get_sp()

if sp:
    try:
        st.title("🎵 Spotify Snippets Pro")
        
        # SIDEBAR
        devices_res = sp.devices()
        device_list = {d['name']: d['id'] for d in devices_res.get('devices', [])}

        if not device_list:
            st.warning("⚠️ Brak aktywnych urządzeń! Otwórz Spotify na telefonie.")
            if st.button("Odśwież urządzenia"): st.rerun()
            st.stop()

        selected_device_name = st.sidebar.selectbox("Graj na:", list(device_list.keys()))
        active_id = device_list[selected_device_name]
        
        st.session_state.shuffle_mode = st.sidebar.toggle("Automatyczne mieszanie", value=st.session_state.shuffle_mode)

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
        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            # Jeśli kolejka jest pusta, przycisk ładuje nową. Jeśli nie jest, wznawia od ostatniego indeksu.
            button_label = "▶️ WZNÓW" if (st.session_state.tracks_queue and not st.session_state.playing) else "▶️ START"
            if st.button(button_label, use_container_width=True):
                if target_id:
                    # Ładujemy nową kolejkę tylko jeśli jest pusta lub jeśli startujemy nową playlistę
                    if not st.session_state.tracks_queue:
                        with st.spinner('Pobieranie wszystkich utworów...'):
                            res = get_all_playlist_tracks(sp, target_id)
                            valid_tracks = []
                            for item in res:
                                t = item.get('track') or item.get('item')
                                if t and t.get('id'):
                                    valid_tracks.append(t)
                            st.session_state.tracks_queue = valid_tracks
                            if st.session_state.shuffle_mode:
                                random.shuffle(st.session_state.tracks_queue)
                            st.session_state.track_index = 0
                    
                    st.session_state.playing = True
                    st.rerun()

        with c2:
            if st.button("⏮️ POPRZEDNI", use_container_width=True, disabled=not st.session_state.tracks_queue):
                st.session_state.track_index = max(0, st.session_state.track_index - 1)
                st.session_state.playing = True
                st.rerun()

        with c3:
            if st.button("⏭️ NASTĘPNY", use_container_width=True, disabled=not st.session_state.tracks_queue):
                st.session_state.track_index += 1
                st.session_state.playing = True
                st.rerun()

        with c4:
            if st.button("🔀 NOWY MIX", use_container_width=True, disabled=not st.session_state.tracks_queue):
                random.shuffle(st.session_state.tracks_queue)
                st.session_state.track_index = 0
                st.session_state.playing = True
                st.toast("Pomieszano całą listę!")
                st.rerun()

        with c5:
            if st.button("🛑 STOP", use_container_width=True):
                st.session_state.playing = False
                try: sp.pause_playback(device_id=active_id)
                except: pass
                st.rerun()

        # Przycisk do całkowitego resetu (wyczyszczenia kolejki)
        if st.session_state.tracks_queue:
            if st.button("🧹 WYCZYŚĆ I ZAŁADUJ NOWĄ LISTĘ", use_container_width=True):
                st.session_state.tracks_queue = []
                st.session_state.track_index = 0
                st.session_state.playing = False
                st.rerun()

        # 7. LOGIKA ODTWARZANIA
        if st.session_state.playing and st.session_state.tracks_queue:
            idx = st.session_state.track_index
            
            if idx < len(st.session_state.tracks_queue):
                track = st.session_state.tracks_queue[idx]
                release_year = track['album'].get('release_date', '????')[:4]
                
                col_img, col_info = st.columns([1, 2])
                with col_img:
                    if track['album']['images']:
                        st.image(track['album']['images'][0]['url'], width=300)
                with col_info:
                    st.header(track['name'])
                    st.subheader(f"🎤 {track['artists'][0]['name']}")
                    st.write(f"💿 Album: **{track['album']['name']}**")
                    st.write(f"📅 Rok wydania: **{release_year}**")
                    st.write(f"🎷 Gatunek: {get_artist_genres(sp, track['artists'][0]['id'])}")
                    st.caption(f"Utwór {idx + 1} z {len(st.session_state.tracks_queue)}")

                prog_bar = st.progress(0)
                
                try:
                    sp.start_playback(device_id=active_id, uris=[track['uri']], position_ms=45000)
                    
                    # Czas trwania snippetu (30s)
                    for s in range(30):
                        if not st.session_state.playing: break
                        time.sleep(1)
                        prog_bar.progress((s + 1) / 30, text=f"Snippet: {s+1}s / 30s")
                    
                    if st.session_state.playing:
                        st.session_state.track_index += 1
                        st.rerun()

                except Exception as play_error:
                    st.error("Upewnij se, że Spotify jest aktywne na wybranym urządzeniu.")
                    st.session_state.playing = False
            else:
                st.success("Koniec playlisty!")
                st.session_state.playing = False
                st.session_state.tracks_queue = [] # Reset po zakończeniu

    except Exception as e:
        st.error(f"Błąd: {e}")
