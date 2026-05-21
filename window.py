import streamlit as st
from chatbot import detect_entities, analyze_intent_and_tags, search_by_genre, search_by_antigenre, search_by_actor_or_director, search_by_collection, search_discovery

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
        if movie["poster"]: st.image(movie["poster"], use_container_width=True)
        else: st.info("📷 Póster no disponible")
    with col2:
        st.subheader(movie["title"])
        st.caption(f"📅 Fecha de estreno: {movie.get('release', 'N/A')}")
        st.write(movie["overview"] if movie["overview"] else "Sin descripción disponible.")

def run_gui():
    st.set_page_config(page_title="Jordi's Filming", page_icon="🍿", layout="centered")
    st.title("🍿 Jordi's Filming")
    st.caption("Tu recomendador inteligente de cine")

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
            if any(entities.values()) or intencion == "DESCUBRIR":
                with st.spinner('Consultando las mejores opciones para ti...'):
                    avisos_lista = []
                    if any(entities.values()):
                        if entities.get("generos"):
                            avisos_lista.append(f"🎬 Género: {', '.join(entities['generos'])}")
                            if intencion == "QUERER":
                                movie_list = search_by_genre(entities['generos'])
                            if intencion == "NO_QUERER":
                                movie_list = search_by_antigenre(entities['generos'])
                        if entities.get("actores"):
                            avisos_lista.append(f"🎭 Actor: {', '.join(entities['actores'])}")
                            if intencion == "QUERER":
                                movie_list = search_by_actor_or_director(entities)
                        if entities.get("directores"):
                            avisos_lista.append(f"🎥 Director: {', '.join(entities['directores'])}")
                            if intencion == "QUERER":
                                movie_list = search_by_actor_or_director(entities)
                        if entities.get("sagas"):
                            avisos_lista.append(f"📚 Saga: {', '.join(entities['sagas'])}")
                            if intencion == "QUERER":
                                movie_list = search_by_collection(entities)
                        if entities.get("productoras"):
                            avisos_lista.append(f"🏢 Productora: {', '.join(entities['productoras'])}")
                        if entities.get("temas"):
                            avisos_lista.append(f"🏷️ Tema: {', '.join(entities['temas'])}")
                        if entities.get("plataformas"):
                            avisos_lista.append(f"📺 Plataforma: {', '.join(entities['plataformas'])}")
                        aviso_texto = "🔎 He detectado: " + " | ".join(avisos_lista)
                        st.info(aviso_texto)
                    else:
                        if intencion == "DESCUBRIR":
                            movie_list = search_discovery()
                            print("Descubrir")
                            print(movie_list)
                    # Aplicar reglas y buscar película
                    if movie_list:
                        st.write("### Mis recomendaciones para ti:")

                        # Eliminamos el uso de st.columns(3) e iteramos directamente
                        for movie_info in movie_list:
                            # Renderizamos directamente cada película sin columnas
                            render_single_card(movie_info)

                        new_msg = {
                            "role": "assistant",
                            "content": "He analizado tus preferencias y aquí tienes el Top 3 que mejor encaja contigo.",
                            "movie_info": movie_list
                        }
                    else:
                        if intencion == "CONTRADICCION":
                            respuesta = "Antes de escribir el mensaje aclarate, por favor..."
                        else:
                            # Caso en que no hay resultados
                            respuesta = "Perdona, no he encontrado películas que se ajusten a esa petición."
                        st.markdown(respuesta)
                        new_msg = {"role": "assistant", "content": respuesta, "intent_display": display_intent,
                                   "tags_detected": tags}
            else:
                #Caso en que no hay resultados
                respuesta = "Perdona, no he encontrado películas que se ajusten a esa petición."
                st.markdown(respuesta)
                new_msg = {"role": "assistant", "content": respuesta, "intent_display": display_intent,
                           "tags_detected": tags}
            st.session_state.messages.append(new_msg)

if __name__ == "__main__": 
    run_gui()