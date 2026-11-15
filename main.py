import streamlit as st
import src.data as data
import time
import os

st.set_page_config(
    layout="wide",
    page_title="Cosmic Viewport",
    page_icon="images/logo-color.png",
)

if "playback_dir" not in st.session_state:
    st.session_state.playback_dir = 1  # 1 = forward, -1 = backward

if "is_playing" not in st.session_state:
    st.session_state.is_playing = False

if "ra" not in st.session_state:
    st.session_state.ra = 150.7818

if "dec" not in st.session_state:
    st.session_state.dec = 3.3502

if "dates_to_wavelengths" not in st.session_state:
    st.session_state.dates_to_wavelengths = {"Downloading": ["Downloading"]}

if "error_text" not in st.session_state:
    st.session_state.error_text = ""

if "downoading" not in st.session_state:
    st.session_state.downloading = False

if "current_image" not in st.session_state:
    # st.session_state.current_image = "testImage.jpg"
    st.session_state.current_image = "images/logo-trans.png"

if "date_choices" not in st.session_state:
    st.session_state.date_choices = ["", "Please Submit Data Before Choosing A Date", " "]

if "wave_choices" not in st.session_state:
    st.session_state.wave_choices = ["", "Please Submit Data Before Choosing A Wavelength", " "]

# Get it, it updates the date :)
def upWAVE():
    if st.session_state.dates_to_wavelengths:
        st.session_state.current_image = f"data/{st.session_state.ra}-{st.session_state.dec}/{st.session_state.date_slider}/{st.session_state.wave_slider}.png"

def upDATE():
    if st.session_state.dates_to_wavelengths:
        st.session_state.wave_choices = st.session_state.dates_to_wavelengths.get(st.session_state.date_slider)
        if type(st.session_state.wave_slider) is not str:
            best = st.session_state.wave_choices[0]
            dist = abs(st.session_state.wave_choices[0] - st.session_state.wave_slider)
            for choice in st.session_state.wave_choices:
                if abs(choice - st.session_state.wave_slider) < dist:
                    best = choice
                    dist = abs(choice - st.session_state.wave_slider)
            st.session_state.wave_slider = best
        else:
            st.session_state.wave_slider = st.session_state.wave_choices[0]
        st.session_state.current_image = f"data/{st.session_state.ra}-{st.session_state.dec}/{st.session_state.date_slider}/{st.session_state.wave_slider}.png"

def submit():
    if (st.session_state.ra or st.session_state.ra == 0) and (st.session_state.dec or st.session_state.dec == 0):
        # st.session_state.dates_to_wavelengths = data.get_image(st.session_state.ra, st.session_state.dec) # OLD

        gen = data.get_image(st.session_state.ra, st.session_state.dec)
        downloads_needed = next(gen)
        progress = 0

        loading_bar = st.progress(0, "Started downloading images...")
        while True:
            try:
                progress = next(gen)
                loading_bar.progress(
                    float(progress / downloads_needed), 
                    f"Started downloading images ({progress}/{downloads_needed})"
                )
                print(f"Progress: {progress}/{downloads_needed}, {float(progress / downloads_needed)}")
            except StopIteration as e:
                st.session_state.dates_to_wavelengths = e.value
                loading_bar.empty()
                break

        st.session_state.date_choices = list(st.session_state.dates_to_wavelengths)
        if st.session_state.date_choices:
            st.session_state.date_slider = st.session_state.date_choices[0]

        st.session_state.wave_choices = st.session_state.dates_to_wavelengths.get(st.session_state.date_slider)
        if st.session_state.wave_choices:
            st.session_state.wave_slider = st.session_state.wave_choices[0]

        new_img_url = f"data/{st.session_state.ra}-{st.session_state.dec}/{st.session_state.date_slider}/{st.session_state.wave_slider}.png"
        if os.path.exists(new_img_url):
            st.session_state.current_image = new_img_url
        else:
            st.session_state.downloading = True
    else:
        st.session_state.error_text = ":red[Please put in all required information!]"

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

col1, col2 = st.columns([2, 1], vertical_alignment="top", gap="large")

with col1:
    st.image(st.session_state.current_image, use_container_width=True, )

with col2:
    raw_ra = st.text_input("Right Ascension", placeholder="Enter Numbers", value="150.7818", disabled=st.session_state.is_playing)
    
    if raw_ra:
        try:
            st.session_state.ra = float(raw_ra)
        except:
            st.write(":red[Please enter only numbers]")

    raw_dec = st.text_input("Declination", placeholder="Enter Numbers", value="3.3502", disabled=st.session_state.is_playing)
    
    if raw_dec:
        try:
            st.session_state.dec = float(raw_dec)
        except:
            st.write(":red[Please enter only numbers]")

    submitButton = st.button("Submit", on_click=submit, disabled=st.session_state.is_playing)
    
    if (st.session_state.ra or st.session_state.ra == 0) and (st.session_state.dec or st.session_state.dec == 0):
        st.session_state.error_text = ""
        
    errorText = st.write(st.session_state.error_text)

    if not st.session_state.downloading:
        if st.session_state.wave_choices:
            wavelength = st.select_slider(
                "Wavelength μm",
                key="wave_slider",
                options=st.session_state.wave_choices,
                value=st.session_state.wave_choices[1] if "Please Submit Data Before Choosing A Wavelength" in st.session_state.wave_choices else st.session_state.wave_choices[0],
                on_change=upWAVE,
                disabled="Please Submit Data Before Choosing A Wavelength" in st.session_state.wave_choices,
            )

        if st.session_state.date_choices:
            date = st.select_slider(
                "Date",
                key="date_slider",
                options=st.session_state.date_choices,
                value=st.session_state.date_choices[1] if "Please Submit Data Before Choosing A Date" in st.session_state.date_choices else st.session_state.date_choices[0],
                on_change=upDATE,
                disabled="Please Submit Data Before Choosing A Date" in st.session_state.date_choices,
            )

        st.button("Stop" if st.session_state.is_playing else "Play", on_click=toggle_play)

logo = st.logo("images/logo-color.png", icon_image="images/logo-color.png")

# loading_bar = st.progress(100, text="Downloading Images")
# loading_bar.empty()

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