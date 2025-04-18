import streamlit as st
from PIL import Image


# Set page configuration
st.set_page_config(
    page_title="Homepage App",
    page_icon="",
)

# Title of the app
main_title = "RYAA"

st.markdown(f"""# {main_title} <span style=color:#2E9BF5><font size=5>Beta</font></span>""",unsafe_allow_html=True)

ryaaText = Image.open("ryaaText.png")
new_size = (225, 225)
backgroundColor="#FFA421"
ryaaText = ryaaText.resize(new_size)
#st.image(ryaaText)

home_title = "RYAA"
home_introduction = "Welcome to RYAA, a project developed for a senior project at North Carolina Agricultural and Technical State University. " \
"RYAA aims to advance the capabilities of virtual assistants by overcoming a critical limitation in current AI systems. "

home_privacy = "To protect your personal information, our system only uses the hashed value of your OpenAI API Key, ensuring complete privacy and anonymity. " \
"Your API key is only used to access AI functionality during each visit, and is not stored beyond that time. "

home_get_started = "To chat with RYAA please click on the PromptPage in the sidebar."

st.markdown("######")
st.markdown("### Hello Human")
st.write(home_introduction)

st.markdown("######")
st.markdown("### Privacy")
st.write(home_privacy)

st.markdown("######")
st.markdown("### Get Started")
st.write(home_get_started)



    # Initialize session state for "my_input" if not already present
if "my_input" not in st.session_state:
    st.session_state["my_input"] = ""

