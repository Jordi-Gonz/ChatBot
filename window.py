import streamlit as st
from chatbot import detect_entities, analyze_intent_and_tags, search_by_all_entities
from data import nuevo_usuario


def render_movie_card(movie_data):
    if isinstance(movie_data, list):
        for movie in movie_data:
            render_single_card(movie)
            st.divider()
    else:
        render_single_card(movie_data)

def render_single_card(movie):
    col1, col2 = st.columns([1, 2])
    with col1:
        if movie["poster"]: st.image(movie["poster"], width="stretch")
        else: st.info("📷 Póster no disponible")
    with col2:
        st.subheader(movie["title"])
        st.caption(f"📅 Fecha de estreno: {movie.get('release', 'N/A')}")
        st.write(movie["overview"] if movie["overview"] else "Sin descripción disponible.")

def run_gui():
    st.set_page_config(page_title="Jordi's Filming", page_icon="🍿", layout="centered")
    st.title("🍿 Jordi's Filming")
    st.caption("Tu recomendador inteligente de cine")

    with st.sidebar:
        st.title("⚙️ Configuración")
        if "letterboxd_user" not in st.session_state:
            st.session_state.letterboxd_user = ""

        user_input = st.text_input("Usuario de Letterboxd", value=st.session_state.letterboxd_user)
        if st.button("Guardar Usuario"):
            st.session_state.letterboxd_user = user_input
            st.success(f"Usuario guardado: {user_input}")
            nuevo_usuario(user_input)

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "¡Hola! ¿Qué te apetece ver hoy?"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if "intent_display" in msg: st.subheader(msg["intent_display"])
            st.markdown(msg["content"])
            if "tags_detected" in msg and msg["tags_detected"]:
                tag_html = "".join([f'<span style="background-color:#454545; color:white; padding:2px 10px; border-radius:12px; margin-right:5px; font-size:12px; border:1px solid #666;">#{t}</span>' for t in msg["tags_detected"]])
                st.markdown(tag_html, unsafe_allow_html=True)
                st.write("")
            if "entities_detected" in msg: st.info(msg["entities_detected"])
            if "movie_info" in msg: render_movie_card(msg["movie_info"])

    if prompt := st.chat_input("Ej: Estoy con mis hijos y nos gusta Disney"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            # Análisis de intención y tags
            intencion, tags = analyze_intent_and_tags(prompt)
            intent_map = {"QUERER": "✅ Querer", "NO_QUERER": "❌ No querer", "DESCUBRIR": "✨ Descubrir", "CONTRADICCION": "🤨 Contradicción"}
            display_intent = intent_map.get(intencion, "🔍 Analizando")
            st.subheader(display_intent)

            # Visualización de Tags
            if tags:
                tag_html = "".join([f'<span style="background-color:#454545; color:white; padding:2px 10px; border-radius:12px; margin-right:5px; font-size:12px; border:1px solid #666;">#{t}</span>' for t in tags])
                st.markdown(tag_html, unsafe_allow_html=True)
                st.write("")

            # Detección y visualización de Entidades
            entities = detect_entities(prompt)
            movie_list = []
            
            # --- SECCIÓN OPTIMIZADA CON LA NUEVA FUNCIÓN ---
            if any(entities.values()) or intencion == "DESCUBRIR":
                with st.spinner('Consultando las mejores opciones para ti...'):
                    avisos_lista = []
                    
                    # Mostrar la información detectada en la UI
                    if entities.get("generos"): avisos_lista.append(f"🎬 Género: {', '.join(entities['generos'])}")
                    if entities.get("actores"): avisos_lista.append(f"🎭 Actor: {', '.join(entities['actores'])}")
                    if entities.get("directores"): avisos_lista.append(f"🎥 Director: {', '.join(entities['directores'])}")
                    if entities.get("sagas"): avisos_lista.append(f"📚 Saga: {', '.join(entities['sagas'])}")
                    if entities.get("productoras"): avisos_lista.append(f"🏢 Productora: {', '.join(entities['productoras'])}")
                    if entities.get("temas"): avisos_lista.append(f"🏷️ Tema: {', '.join(entities['temas'])}")
                    if entities.get("plataformas"): avisos_lista.append(f"📺 Plataforma: {', '.join(entities['plataformas'])}")
                    
                    if avisos_lista:
                        aviso_texto = "🔎 He detectado: " + " | ".join(avisos_lista)
                        st.info(aviso_texto)

                    movie_list = search_by_all_entities(entities, intencion)

                    # Mostrar resultados en pantalla si existen
                    if movie_list:
                        st.write("### Mis recomendaciones para ti:")
                        for movie_info in movie_list:
                            render_single_card(movie_info)

                        # Guardamos el mensaje con la metadata correcta para el historial
                        new_msg = {
                            "role": "assistant",
                            "content": "He analizado tus preferencias y aquí tienes el Top 3 que mejor encaja contigo.",
                            "intent_display": display_intent,
                            "tags_detected": tags,
                            "entities_detected": aviso_texto if avisos_lista else None,
                            "movie_info": movie_list
                        }
                    else:
                        if intencion == "CONTRADICCION":
                            respuesta = "Antes de escribir el mensaje aclarate, por favor..."
                        else:
                            respuesta = "Perdona, no he encontrado películas que se ajusten a esa petición."
                        st.markdown(respuesta)
                        new_msg = {"role": "assistant", "content": respuesta, "intent_display": display_intent, "tags_detected": tags}
            else:
                respuesta = "Perdona, no he encontrado películas que se ajusten a esa petición."
                st.markdown(respuesta)
                new_msg = {"role": "assistant", "content": respuesta, "intent_display": display_intent, "tags_detected": tags}
            
            st.session_state.messages.append(new_msg)

if __name__ == "__main__": 
    run_gui()