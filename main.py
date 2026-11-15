import streamlit as st
import src.data as data

st.set_page_config(
    layout="wide",
    page_title="Cosmic Viewport",
    page_icon="🟣",
)

date = None
prevDate = None
datesToWavelengths = None
ra = None
dec = None

if "error_text" not in st.session_state:
    st.session_state.error_text = ""

if "current_image" not in st.session_state:
    st.session_state.current_image = "data/output.jpg"

if "date_choices" not in st.session_state:
    st.session_state.date_choices = ["", "Please Submit Data Before Choosing A Date", " "]

if "wave_choices" not in st.session_state:
    st.session_state.wave_choices = ["", "Please Submit Data Before Choosing A Wavelength", " "]

# Get it, it updates the date :)
def upDATE():
    if datesToWavelengths:
        st.session_state.wave_choices = datesToWavelengths.get(st.session_state.date_slider)
        st.session_state.wave_slider = st.session_state.wave_choices[0]
        st.session_state.current_image = "data/{ra}-{dec}/{st.session_state.date_slider}/{st.session_state.wave_slider}.png"

def submit():
    if (ra or ra == 0) and (dec or dec == 0):
        datesToWavelengths = data.get_image(ra, dec)
        st.session_state.date_choices = list(datesToWavelengths)
        st.session_state.date_slider = st.session_state.date_choices[0]
        st.write(datesToWavelengths)
        upDATE()
        # st.session_state.date_choices = {"0001-1-1" : "data/output.jpg", "0002-2-2" : "testImage.jpg", "0003-3-3" : "data/output.jpg"}
    else:
        st.session_state.error_text = ":red[Please put in all required information!]"

col1, col2 = st.columns([2, 1], vertical_alignment="top", gap="large")

with col1:
    st.image(st.session_state.current_image, use_container_width=True)

with col2:

    raw_ra = st.text_input("Right Ascension", placeholder="Enter Numbers", value="150.7818")
    
    if raw_ra:
        try:
            ra = float(raw_ra)
        except:
            st.write(":red[Please enter only numbers]")

    raw_dec = st.text_input("Declination", placeholder="Enter Numbers", value="3.3502")
    
    if raw_dec:
        try:
            dec = float(raw_dec)
        except:
            st.write(":red[Please enter only numbers]")

    submitButton = st.button("Submit", on_click=submit)
    
    if (ra or ra == 0) and (dec or dec == 0):
        st.session_state.error_text = ""
        
    errorText = st.write(st.session_state.error_text)
    
    wavelength = st.select_slider(
        "Wavelength μm",
        key="wave_slider",
        options=st.session_state.wave_choices,
        value=st.session_state.wave_choices[1] if "Please Submit Data Before Choosing A Wavelength" in st.session_state.wave_choices else st.session_state.wave_choices[0],
        on_change=upDATE,
        disabled="Please Submit Data Before Choosing A Wavelength" in st.session_state.wave_choices,
    )

    date = st.select_slider(
        "Date",
        key="date_slider",
        options=st.session_state.date_choices,
        value=st.session_state.date_choices[1] if "Please Submit Data Before Choosing A Date" in st.session_state.date_choices else st.session_state.date_choices[0],
        on_change=upDATE,
        disabled="Please Submit Data Before Choosing A Date" in st.session_state.date_choices,

    st.write(datesToWavelengths)
    )

logo = st.logo("logo.png", icon_image="logo.png")

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
</style>
<div class="footer">
    <p>made with love by humans <3</p>
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)