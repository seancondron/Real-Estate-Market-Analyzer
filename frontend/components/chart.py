import streamlit as st

def render_chart(data):
    """Reusable chart component."""
    st.line_chart(data)
