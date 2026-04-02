import streamlit as st
from chatbot import process_text, apply_rules

st.set_page_config(page_title="Jordi's Filming", page_icon="🎬")
st.title("🎬 Jordi's Filming")
st.caption("Chatbot recomendador basado en reglas y NLP")

# Como Streamlit recarga todo el script en cada interacción,
# necesitamos guardar el historial de mensajes en la memoria de la sesión.
# Para eso guardaremos los mensajes y los mostraremos en cada interacción
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "¡Hola! Soy Jordi's Filming. Dime qué tipo de película o serie te apetece ver hoy."
    })

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Escribe tu idea aquí... (ej: quiero ver una peli de comedia)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando tu petición..."):
            important_words = process_text(prompt)

            # Mostrar las palabras clave extraídas como dato de depuración
            st.caption(f"Palabras detectadas: {important_words}")

            respuesta_bot = apply_rules(important_words)

        st.markdown(respuesta_bot)
        st.session_state.messages.append({"role": "assistant", "content": respuesta_bot})