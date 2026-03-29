import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import random

# 1. KONFIGURACJA STRONY I SESJI
st.set_page_config(page_title="Spotify Snippets Pro", page_icon="🎵", layout="wide")

# Inicjalizacja stanów sesji (pamięć aplikacji między odświeżeniami)
if 'playing' not in st.session_state: st.session_state.playing = False
if 'track_index' not in st.session_state: st.session_state.track_index = 0
if 'tracks_queue' not in st.session_state: st.session_state.tracks_queue = []

# 2. FUNKCJA AUTORYZACJI (DOSTOSOWANA DO CHMURY I SMARTFONA)
@st.cache_resource
def get_sp():
    # Pobieranie danych z Secrets (Streamlit Cloud)
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

    # Przechwytywanie kodu z adresu URL po powrocie ze Spotify
    query_params = st.query_params
    if "code" in query_params:
        auth_manager.get_access_token(query_params["code"])
        st.query_params.clear()
        st.rerun()

    # Sprawdzenie czy mamy ważny token
    token_info = auth_manager.get_cached_token()

    if not token_info:
        auth_url = auth_manager.get_authorize_url()
        st.title("🔐 Logowanie Spotify")
        st.write("Twoja sesja wygasła lub nie jesteś zalogowany.")
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

# 4. URUCHOMIENIE APLIKACJI
sp = get_sp()

if sp:
    try:
        # Pobranie danych użytkownika
        user_me = sp.me()
        st.sidebar.write(f"Zalogowano: **{user_me['display_name']}**")
        
        st.title("🎵 Spotify Snippets Pro")
        
        # WYBÓR URZĄDZENIA
        devices_res = sp.devices()
        device_list = {d['name']: d['id'] for d in devices_res.get('devices', [])}

        if not device_list:
            st.warning("⚠️ Brak aktywnych urządzeń! Otwórz Spotify na telefonie.")
            if st.button("Odśwież listę urządzeń"): st.rerun()
            st.stop()

        selected_device_name = st.sidebar.selectbox("Graj na:", list(device_list.keys()))
        active_id = device_list[selected_device_name]

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
            url_input = st.text_input("Wklej URL playlisty (np. Radar Premier):")
            if url_input:
                target_id = url_input.split('/')[-1].split('?')[0]

        # 6. KONTROLA ODTWARZANIA (Przyciski)
        st.divider()
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            if st.button("▶️ START", use_container_width=True):
                if target_id:
                    with st.spinner("Ładowanie utworów..."):
                        res = sp.playlist_tracks(target_id)['items']
                        # Bezpieczne parsowanie utworów (odporne na błąd 'track')
                        valid_tracks = []
                        for item in res:
                            t = item.get('track') or item.get('item')
                            if t and t.get('id'):
                                valid_tracks.append(t)
                        
                        st.session_state.tracks_queue = valid_tracks
                        random.shuffle(st.session_state.tracks_queue)
                        st.session_state.track_index = 0
                        st.session_state.playing = True
                        st.rerun()

        with c2:
            if st.button("⏮️", use_container_width=True, disabled=not st.session_state.playing):
                st.session_state.track_index = max(0, st.session_state.track_index - 1)
                st.rerun()

        with c3:
            if st.button("⏭️", use_container_width=True, disabled=not st.session_state.playing):
                st.session_state.track_index += 1
                st.rerun()

        with c4:
            if st.button("🛑 STOP", use_container_width=True):
                st.session_state.playing = False
                try: sp.pause_playback(device_id=active_id)
                except: pass
                st.rerun()

        # 7. GŁÓWNA LOGIKA ODTWARZANIA
        if st.session_state.playing and st.session_state.tracks_queue:
            idx = st.session_state.track_index
            
            if idx < len(st.session_state.tracks_queue):
                current_track = st.session_state.tracks_queue[idx]
                
                # Wyświetlanie informacji o utworze
                col_img, col_info = st.columns([1, 2])
                with col_img:
                    if current_track['album']['images']:
                        st.image(current_track['album']['images'][0]['url'], width=300)
                with col_info:
                    st.header(current_track['name'])
                    st.subheader(current_track['artists'][0]['name'])
                    st.write(f"Album: {current_track['album']['name']}")
                    st.write(f"Gatunek: {get_artist_genres(sp, current_track['artists'][0]['id'])}")
                    st.caption(f"Utwór {idx + 1} z {len(st.session_state.tracks_queue)}")

                # Pasek postępu snippetu
                prog_bar = st.progress(0)
                
                try:
                    # Rozpoczęcie odtwarzania od 45 sekundy (45000 ms)
                    sp.start_playback(device_id=active_id, uris=[current_track['uri']], position_ms=45000)
                    
                    # Odliczanie 20 sekund
                    for s in range(20):
                        if not st.session_state.playing: break
                        time.sleep(1)
                        prog_bar.progress((s + 1) / 20, text=f"Słuchasz fragmentu: {s+1}s / 20s")
                    
                    # Automatyczne przejście do następnego utworu
                    if st.session_state.playing:
                        st.session_state.track_index += 1
                        st.rerun()

                except Exception as play_error:
                    st.error(f"Problem z Spotify: {play_error}")
                    st.info("Upewnij się, że masz włączone odtwarzanie w aplikacji Spotify.")
                    st.session_state.playing = False
            else:
                st.success("Koniec playlisty!")
                st.session_state.playing = False

    except Exception as e:
        st.error(f"Wystąpił błąd krytyczny: {e}")
