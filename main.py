import streamlit as st
import src.data as data
import time
import os

st.set_page_config(
    layout="wide",
    page_title="Cosmic Viewport",
    page_icon="images/logo-color.png",
)

if "target_wave" not in st.session_state:
    st.session_state.target_wave = 0

if "playback_dir" not in st.session_state:
    st.session_state.playback_dir = 1

if "is_playing" not in st.session_state:
    st.session_state.is_playing = False

if "ra" not in st.session_state:
    st.session_state.ra = 150.7818

if "dec" not in st.session_state:
    st.session_state.dec = 3.3502

if "dates_to_wavelengths" not in st.session_state:
    st.session_state.dates_to_wavelengths = {}

if "error_text" not in st.session_state:
    st.session_state.error_text = ""

if "downloading" not in st.session_state:
    st.session_state.downloading = False

# Set by the Submit callback, acted on further down by the script body. Doing the
# download there is what lets st.progress render and update in the browser.
if "download_request" not in st.session_state:
    st.session_state.download_request = False

if "current_image" not in st.session_state:
    # st.session_state.current_image = "testImage.jpg"
    st.session_state.current_image = "images/logo-trans.png"

if "date_choices" not in st.session_state:
    st.session_state.date_choices = ["", "Please Submit Data Before Choosing A Date", " "]

if "wave_choices" not in st.session_state:
    st.session_state.wave_choices = ["", "Please Submit Data Before Choosing A Wavelength", " "]

def upWAVE():
    if st.session_state.dates_to_wavelengths:
        st.session_state.target_wave = st.session_state.wave_slider
        st.session_state.current_image = f"data/{st.session_state.ra}-{st.session_state.dec}/{st.session_state.date_slider}/{st.session_state.wave_slider}.png"

# Get it, it updates the date :)
def upDATE():
    if st.session_state.dates_to_wavelengths:
        st.session_state.wave_choices = st.session_state.dates_to_wavelengths.get(st.session_state.date_slider) or []
        if not st.session_state.wave_choices:
            return
        if type(st.session_state.wave_slider) is not str:
            best = st.session_state.wave_choices[0]
            dist = abs(st.session_state.wave_choices[0] - st.session_state.target_wave)
            for choice in st.session_state.wave_choices:
                if abs(choice - st.session_state.target_wave) < dist:
                    best = choice
                    dist = abs(choice - st.session_state.target_wave)
            st.session_state.wave_slider = best
        else:
            st.session_state.wave_slider = st.session_state.wave_choices[0]
        st.session_state.current_image = f"data/{st.session_state.ra}-{st.session_state.dec}/{st.session_state.date_slider}/{st.session_state.wave_slider}.png"

def parse_coordinate(raw_value, label):
    """Turn a text field into a float, writing a readable message when it is not usable."""
    text = (raw_value or "").strip()
    if not text:
        st.session_state.error_text = ":red[Please put in all required information!]"
        return None
    try:
        return float(text)
    except ValueError:
        st.session_state.error_text = f":red[Please enter a number for {label}.]"
        return None

def submit():
    st.session_state.error_text = ""
    st.session_state.downloading = False

    ra = parse_coordinate(st.session_state.get("ra_input"), "Right Ascension")
    dec = parse_coordinate(st.session_state.get("dec_input"), "Declination")
    if ra is None or dec is None:
        return

    if not 0 <= ra <= 360:
        st.session_state.error_text = ":red[Right Ascension must be between 0 and 360 degrees.]"
        return

    if not -90 <= dec <= 90:
        st.session_state.error_text = ":red[Declination must be between -90 and 90 degrees.]"
        return

    st.session_state.ra = ra
    st.session_state.dec = dec
    st.session_state.download_request = True # the body of the script does the work, so progress can render

def load_images(ra, dec):
    """Drive the get_image generator from the script body, where st.progress updates live."""
    dates_to_wavelengths = {}
    downloads_needed = None
    loading_bar = st.progress(0.0, "Looking for images...")

    try:
        gen = data.get_image(ra, dec)
        while True:
            try:
                value = next(gen)
            except StopIteration as finished:
                # A generator finishes by raising StopIteration, handing back its return
                # value (the dates -> wavelengths dict) as finished.value
                dates_to_wavelengths = finished.value or {}
                break

            if downloads_needed is None:
                downloads_needed = value # the first thing yielded is how many images are needed
                loading_bar.progress(0.0, f"Downloading {downloads_needed} images...")
            elif downloads_needed:
                # st.progress wants a single float, and value can pass the total when a
                # cached image shows up twice, so clamp it instead of overflowing 1.0.
                ratio = min(1.0, value / downloads_needed)
                loading_bar.progress(ratio, f"Downloaded {value}/{downloads_needed} images")
    except Exception as e:
        st.session_state.error_text = f":red[Could not load images: {e}]"
    finally:
        loading_bar.empty()

    return dates_to_wavelengths

def apply_results(dates_to_wavelengths):
    """Store the fetched data and point the sliders at an image that actually exists."""
    st.session_state.dates_to_wavelengths = dates_to_wavelengths or {}

    # Nothing was downloaded or cached for this position
    if not st.session_state.dates_to_wavelengths:
        if not st.session_state.error_text:
            st.session_state.error_text = ":red[No images were found for those coordinates.]"
        st.session_state.date_choices = ["", "Please Submit Data Before Choosing A Date", " "]
        st.session_state.wave_choices = ["", "Please Submit Data Before Choosing A Wavelength", " "]
        return

    st.session_state.date_choices = list(st.session_state.dates_to_wavelengths)

    failed = getattr(dates_to_wavelengths, "failed", 0)
    if failed and not st.session_state.error_text:
        st.session_state.error_text = f":orange[{failed} image(s) could not be downloaded, submit again to retry them.]"

    # Keep the current selection if it is still valid, otherwise fall back to the first one
    if st.session_state.get("date_slider") not in st.session_state.date_choices:
        st.session_state.date_slider = st.session_state.date_choices[0]

    st.session_state.wave_choices = st.session_state.dates_to_wavelengths.get(st.session_state.date_slider) or []

    if st.session_state.get("wave_slider") not in st.session_state.wave_choices:
        st.session_state.wave_slider = st.session_state.wave_choices[0]

    new_img_url = f"data/{st.session_state.ra}-{st.session_state.dec}/{st.session_state.date_slider}/{st.session_state.wave_slider}.png"
    if os.path.exists(new_img_url):
        st.session_state.current_image = new_img_url
    else:
        st.session_state.error_text = ":red[That image is missing from the cache, please submit again.]"

def toggle_play():
    if "Please Submit Data Before Choosing A Date" not in st.session_state.date_choices:
        st.session_state.is_playing = not st.session_state.is_playing
        st.session_state.playback_dir = 1
        st.session_state.date_slider = st.session_state.date_choices[0]

if st.session_state.is_playing:
    try:
        current_idx = st.session_state.date_choices.index(st.session_state.date_slider)
        next_idx = current_idx + st.session_state.playback_dir

        # Reverse direction when hitting boundary ends
        if next_idx >= len(st.session_state.date_choices):
            st.session_state.playback_dir = -1
            next_idx = max(0, current_idx - 1)
        elif next_idx < 0:
            st.session_state.playback_dir = 1
            next_idx = min(len(st.session_state.date_choices) - 1, current_idx + 1)

        st.session_state.date_slider = st.session_state.date_choices[next_idx]
        upDATE()
    except (ValueError, KeyError):
        st.session_state.is_playing = False

# A pending submit is handled here, in the body of the script, so st.progress can
# render and update in the browser while the images are fetched.
if st.session_state.download_request:
    st.session_state.download_request = False
    st.session_state.downloading = True
    try:
        apply_results(load_images(st.session_state.ra, st.session_state.dec))
    finally:
        st.session_state.downloading = False

col1, col2 = st.columns([2, 1], vertical_alignment="top", gap="large")

with col1:
    st.image(st.session_state.current_image, width="stretch")

with col2:
    st.text_input("Right Ascension", key="ra_input", placeholder="Enter Numbers", value="150.7818", disabled=st.session_state.is_playing)

    st.text_input("Declination", key="dec_input", placeholder="Enter Numbers", value="3.3502", disabled=st.session_state.is_playing)

    st.button("Submit", on_click=submit, disabled=st.session_state.is_playing)

    st.write(st.session_state.error_text)

    if not st.session_state.downloading:
        if st.session_state.wave_choices:
            wave_default = {}
            if "wave_slider" not in st.session_state:
                # A default is only needed for the first render. Passing one once the
                # value lives in the session state only earns a Streamlit warning.
                wave_default["value"] = st.session_state.wave_choices[1] if "Please Submit Data Before Choosing A Wavelength" in st.session_state.wave_choices else st.session_state.wave_choices[0]
            st.select_slider(
                "Wavelength μm",
                key="wave_slider",
                options=st.session_state.wave_choices,
                on_change=upWAVE,
                disabled="Please Submit Data Before Choosing A Wavelength" in st.session_state.wave_choices,
                **wave_default,
            )

        if st.session_state.date_choices:
            date_default = {}
            if "date_slider" not in st.session_state:
                date_default["value"] = st.session_state.date_choices[1] if "Please Submit Data Before Choosing A Date" in st.session_state.date_choices else st.session_state.date_choices[0]
            st.select_slider(
                "Date",
                key="date_slider",
                options=st.session_state.date_choices,
                on_change=upDATE,
                disabled="Please Submit Data Before Choosing A Date" in st.session_state.date_choices,
                **date_default,
            )

        st.button("Stop" if st.session_state.is_playing else "Play", on_click=toggle_play)

logo = st.logo("images/logo-color.png", icon_image="images/logo-color.png")

footer_html = """
<style>
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: transparent;
    color: #6c757d;
    text-align: center;
    padding: 3px;
    font-size: 13px;
}
.image {
    height: 50%;
    }
</style>
<div class="footer">
    <p>made with love by humans <3</p>
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)

if st.session_state.is_playing:
    time.sleep(0.5)
    st.rerun()