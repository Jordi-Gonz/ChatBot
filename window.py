import streamlit as st
import re  # Necesario para extraer el título entre comillas
from chatbot import process_text, apply_rules, detect_entities, search_movie_visual

def render_movie_card(movie):
    """
    Crea una tarjeta visual con dos columnas: 
    una para el póster y otra para la información técnica.
    """
    col1, col2 = st.columns([1, 2])
    with col1:
        if movie["poster"]:
            st.image(movie["poster"], use_container_width=True)
    with col2:
        st.subheader(movie["title"])
        st.caption(f"📅 Fecha de estreno: {movie['release']}")
        st.write(movie["overview"])

def run_gui():
    # Configuración de la página
    st.set_page_config(page_title="Jordi's Filming", page_icon="🍿", layout="centered")
    
    st.title("🍿 Jordi's Filming")
    st.caption("Tu recomendador de cine inteligente con datos de TMDB")

    # Inicializar el historial de mensajes en la sesión
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "¡Hola! Soy Jordi's Filming. Dime un director, actor o género y te recomendaré algo especial."}
        ]

    # Dibujar el historial de mensajes
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Si el mensaje guardado contiene datos de una película, renderiza la tarjeta
            if "movie_info" in msg:
                render_movie_card(msg["movie_info"])

    # Input del usuario
    if prompt := st.chat_input("Ej: Quiero ver algo de Tarantino"):
        # 1. Mostrar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Lógica del asistente
        with st.chat_message("assistant"):
            # Procesar texto y detectar entidades (para el expansor de depuración)
            important_words = process_text(prompt)
            entities = detect_entities(important_words)
            
            if any(entities.values()):
                with st.expander("🔍 Entidades detectadas"):
                    for k, v in entities.items():
                        if v: st.write(f"**{k.capitalize()}:** {', '.join(v)}")

            # Obtener la respuesta basada en reglas
            respuesta = apply_rules(important_words)
            st.markdown(respuesta)
            
            # --- LÓGICA DE BÚSQUEDA VISUAL ---
            # Buscamos UNICAMENTE lo que el bot recomienda entre comillas simples en su respuesta
            # Ejemplo: "Te sugiero 'Pulp Fiction'" -> Extrae: Pulp Fiction
            match = re.search(r"'(.*?)'", respuesta)
            
            movie_info = None
            if match:
                movie_to_search = match.group(1)
                with st.spinner(f"Buscando info de '{movie_to_search}'..."):
                    movie_info = search_movie_visual(movie_to_search)
            
            # Preparar el mensaje para guardar en el historial
            new_msg = {"role": "assistant", "content": respuesta}
            
            # Si se encontró la película, mostrar tarjeta y guardarla en el mensaje
            if movie_info:
                st.divider()
                render_movie_card(movie_info)
                new_msg["movie_info"] = movie_info
            
            # Guardar el mensaje completo en el historial
            st.session_state.messages.append(new_msg)

if __name__ == "__main__":
    run_gui()