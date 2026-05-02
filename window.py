import streamlit as st
import re
from chatbot import process_text, apply_rules, detect_entities, search_movie_visual, analyze_intent_and_tags

def render_movie_card(movie):
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
            aviso_texto = ""
            if any(entities.values()):
                avisos_lista = []
                if entities.get("generos"): avisos_lista.append(f"🎬 Género: {', '.join(entities['generos'])}")
                if entities.get("actores"): avisos_lista.append(f"🎭 Actor: {', '.join(entities['actores'])}")
                if entities.get("directores"): avisos_lista.append(f"🎥 Director: {', '.join(entities['directores'])}")
                if entities.get("sagas"): avisos_lista.append(f"📚 Saga: {', '.join(entities['sagas'])}")
                if entities.get("productoras"): avisos_lista.append(f"🏢 Productora: {', '.join(entities['productoras'])}")
                if entities.get("temas"): avisos_lista.append(f"🏷️ Tema: {', '.join(entities['temas'])}")
                if entities.get("plataformas"): avisos_lista.append(f"📺 Plataforma: {', '.join(entities['plataformas'])}")
                aviso_texto = "🔎 He detectado: " + " | ".join(avisos_lista)
                st.info(aviso_texto)

            # Aplicar reglas y buscar película
            respuesta = apply_rules(process_text(prompt))
            st.markdown(respuesta)
            
            match = re.search(r"'(.*?)'", respuesta)
            movie_info = search_movie_visual(match.group(1)) if match else None
            
            new_msg = {"role": "assistant", "content": respuesta, "intent_display": display_intent, "tags_detected": tags}
            if aviso_texto: new_msg["entities_detected"] = aviso_texto
            if movie_info: 
                render_movie_card(movie_info)
                new_msg["movie_info"] = movie_info
            
            st.session_state.messages.append(new_msg)

if __name__ == "__main__": 
    run_gui()