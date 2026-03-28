import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import random

# 1. KONFIGURACJA STRONY I SESJI
st.set_page_config(page_title="Spotify Snippets Pro", page_icon="🎵", layout="wide")

if 'playing' not in st.session_state: st.session_state.playing = False
if 'track_index' not in st.session_state: st.session_state.track_index = 0
if 'tracks_queue' not in st.session_state: st.session_state.tracks_queue = []

# 2. FUNKCJA AUTORYZACJI (DOSTOSOWANA DO CHMURY)
@st.cache_resource
def get_sp():
    # Pobieranie danych z Secrets (Streamlit Cloud) lub os.getenv (Lokalnie)
    client_id = st.secrets.get("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = st.secrets.get("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = st.secrets.get("SPOTIPY_REDIRECT_URI") or os.getenv("SPOTIPY_REDIRECT_URI")

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="user-modify-playback-state user-read-playback-state playlist-read-private playlist-read-collaborative user-library-read",
        open_browser=False,
        cache_path=".spotify_cache"
    )

    # Sprawdzenie czy użytkownik właśnie wrócił z logowania (ma 'code' w URL)
    query_params = st.query_params
    if "code" in query_params:
        auth_manager.get_access_token(query_params["code"])
        # Czyścimy URL z kodu, by nie próbować go użyć dwa razy
        st.query_params.clear()
        st.rerun()

    # Próba pobrania tokena z cache
    token_info = auth_manager.get_cached_token()

    if not token_info:
        auth_url = auth_manager.get_authorize_url()
        st.title("🔐 Wymagana autoryzacja")
        st.write("Aby korzystać z aplikacji na telefonie/w chmurze, musisz połączyć ją ze swoim kontem Spotify.")
        st.link_button("Zaloguj się do Spotify", auth_url)
        st.info("Po kliknięciu 'Agree' zostaniesz przekierowany z powrotem tutaj.")
        return None
    
    return spotipy.Spotify(auth_manager=auth_manager)

# 3. FUNKCJE POMOCNICZE
@st.cache_data(ttl=3600)
def get_artist_genres(_sp, artist_id):
    try:
        artist = _sp.artist(artist_id)
        return ", ".join(artist['genres']).capitalize()
    except: return "Nieznany"

# 4. URUCHOMIENIE AUTORYZACJI
sp = get_sp()

# JEŚLI UŻYTKOWNIK JEST ZALOGOWANY, POKAŻ RESZTĘ APLIKACJI
if sp:
    try:
        user_id = sp.me()['id']
        
        st.title("🎵 Spotify Snippets Pro")
        st.sidebar.header("⚙️ Ustawienia")

        # Wybór urządzenia
        devices_res = sp.devices()
        device_list = {d['name']: d['id'] for d in devices_res.get('devices', [])}

        if not device_list:
            st.warning("⚠️ Brak aktywnych urządzeń! Otwórz Spotify na telefonie lub komputerze.")
            if st.button("Odśwież listę urządzeń"):
                st.rerun()
            st.stop()

        selected_device_name = st.sidebar.selectbox("Graj na urządzeniu:", list(device_list.keys()))
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
                if target_id:
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

        # 7. LOGIKA ODTWARZANIA SNIPPETÓW
        if st.session_state.playing and st.session_state.tracks_queue:
            idx = st.session_state.track_index
            
            if idx < len(st.session_state.tracks_queue):
                t = st.session_state.tracks_queue[idx]
                
                # Interfejs utworu
                col_img, col_info = st.columns([1, 3])
                with col_img:
                    if t['album']['images']:
                        st.image(t['album']['images'][0]['url'], width=250)
                with col_info:
                    st.markdown(f"## {t['name']}")
                    st.write(f"**Wykonawca:** {t['artists'][0]['name']}")
                    st.write(f"**Album:** {t['album']['name']} ({t['album']['release_date'][:4]})")
                    st.write(f"**Gatunek:** {get_artist_genres(sp, t['artists'][0]['id'])}")
                    st.caption(f"Utwór {idx + 1} z {len(st.session_state.tracks_queue)}")
                
                track_progress = st.progress(0)

                # Próba odtworzenia
                try:
                    # Start od 45 sekundy
                    sp.start_playback(device_id=active_device_id, uris=[t['uri']], position_ms=45000)
                    
                    for s in range(20):
                        if not st.session_state.playing: break
                        time.sleep(1)
                        track_progress.progress((s + 1) / 20, text=f"Snippet: {s+1}s / 20s")
                    
                    # Automatyczne przejście dalej
                    if st.session_state.playing:
                        st.session_state.track_index += 1
                        st.rerun()
                
                except Exception as e:
                    st.error(f"Problem z odtwarzaniem: {e}. Upewnij się, że Spotify jest włączone.")
                    st.session_state.playing = False
            else:
                st.success("Koniec listy!")
                st.session_state.playing = False

    except Exception as e:
        st.error(f"Wystąpił nieoczekiwany błąd: {e}")
