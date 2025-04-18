import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
import openai
from PIL import Image
import time
import os

openai.api_key = st.secrets["api_keys"]["OPEN_API_KEY"]

# Typewriter effect generator
def typewriter_stream(text, delay=0.02):
    buffer = ""
    for char in text:
        buffer += char
        yield buffer
        time.sleep(delay)

# Get a reply from OpenAI
def get_reply(input_string):
    if "uber" in input_string.lower():
        return "Uber functionality has not yet been implemented. Stay tuned!"
    if "what is ryaa" in input_string.lower():
        return "RYAA (Real-Time Yielding Autonomous Agent) is a project developed as part of a senior project by Jordan Halliburton, Brandon Byrd, Amari Bullock, Mikayla Thornton, Christian Rubio at North Carolina Agricultural and Technical State University."

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": input_string}
    ]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"An error occurred: {e}"

def app():
    if "history" not in st.session_state:
        st.session_state.history = []

    # Header
    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(script_dir, "streamlit", "ryaaText.png")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            ryaaText = Image.open(image_path).resize((225, 225))
            st.image(ryaaText, use_container_width=False)
        except FileNotFoundError:
            st.error("Image not found. Make sure 'ryaaText.png' is in the 'streamlit' folder.")


    # Chat History Scrollable Box
    st.markdown("""
        <style>
        .scroll-box {
            max-height: 300px;
            overflow-y: auto;
            padding: 1rem;
            background-color: #f5f5f5;
            border-radius: 10px;
            border: 1px solid #ccc;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='scroll-box'>", unsafe_allow_html=True)
    for idx, message in enumerate(st.session_state.history):
        if message.startswith("user:"):
            st.markdown(f"**You:** {message[6:]}")
        elif message.startswith("RYAA:"):
            # Only stream the latest response
            if idx == len(st.session_state.history) - 1:
                st.markdown("**RYAA:**")
                st.write_stream(typewriter_stream(message[6:]))
            else:
                st.markdown(f"**RYAA:** {message[6:]}")
    st.markdown("</div>", unsafe_allow_html=True)

    # User Input
    user_input = st.text_area("Input your question:", height=80)
    if st.button("Submit") and user_input.strip() != "":
        st.session_state.history.append("user: " + user_input)
        output = get_reply(user_input)
        st.session_state.history.append("RYAA: " + output)

        # Limit history length
        if len(st.session_state.history) > 50:
            st.session_state.history = st.session_state.history[-50:]

    # Sidebar
    st.sidebar.toggle("Voice Model")

    ModelOption = st.sidebar.selectbox("Model", ("GPT-3", "GPT-3.5", "GPT-3.5 Turbo", "GPT-4"))
    st.write("Model:", ModelOption)

    LLMOption = st.sidebar.selectbox("Large Language Model", ("OPEN-AI", "..", ".."))
    st.write("LLM:", LLMOption)

    # Footer
    st.write("-----------")
    st.write("This project of the MIS uses generative AI enhanced with specific knowledge on a set of topics...")
    st.write("©2025 North Carolina Agricultural and Technical State University.")

if __name__ == "__main__":
    app()
