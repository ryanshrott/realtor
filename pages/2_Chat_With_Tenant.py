import streamlit as st
import boto3
from io import BytesIO
from embedchain import App
from utils import *
from streamlit_authenticator import Authenticate

def main():
    st.title('Tenant ChatBot')

    # Analyze Candidates for an Address Section
    available_listings = fetch_created_listings()
    if not available_listings:
        st.warning("No listings available at the moment.")
        return

    selected_address = st.selectbox("Select a listing:", available_listings)
    tenants = get_tenants_for_address(selected_address)
    selected_tenant = st.selectbox("Select a tenant:", tenants)

    # Initialize embedchain app
    if st.button("Chat with tenant?"):
        st.session_state['bot'] = create_bot(selected_address, selected_tenant)

    if "bot" in st.session_state:
        # Start Chatbot and Reset Conversation buttons
        reset_chat = st.button("Reset Conversation")
        
        if reset_chat:
            st.session_state.messages = []

        # Chatbot functionality with streaming
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ask a question about the documents:"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                responses = st.session_state['bot'].chat(prompt)
                for chunk in responses:
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
if __name__ == "__main__":
    st.session_state['authenticator'] = Authenticate("smartbidscookie3124", "smartbidskey3214", 30)
    if 'authentication_status' not in st.session_state:
        st.session_state['authentication_status'] = None
    if 'verified' not in st.session_state:
        st.session_state['verified'] = None

    st.session_state['authenticator'].login('Login', 'main')
    if st.session_state['verified'] and st.session_state["authentication_status"]:
        st.session_state['authenticator'].logout('Logout', 'sidebar', key='123')
    if st.session_state['verified'] and st.session_state["authentication_status"]:
        if 'subscribed' not in st.session_state:
            st.session_state['subscribed'] = is_email_subscribed(st.session_state['email'])
        main()