import re
import json
import spacy
import requests 
import random
from difflib import SequenceMatcher

# Configuración TMDB
TMDB_API_KEY = "8fdeff49fbf33e98768b3eaaf592bb59" 
BASE_URL = "https://api.themoviedb.org/3"

# Carga de recursos NLP
nlp = spacy.load("es_core_news_sm")

def fuzzy_match(text, target, threshold):
    """Calcula la similitud entre dos textos."""
    return SequenceMatcher(None, text, target).ratio() >= threshold

def load_local_movie_data(filepath="DB/movie_dataset.json"):
    """Carga todas las entidades, etiquetas e intenciones configuradas."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Estas listas ahora contienen objetos/diccionarios según tu JSON[cite: 1, 2]
        colecciones = data.get("colecciones", []) 
        estudios = data.get("estudios", [])
        plataformas = data.get("plataformas", []) 
        
        # Estas siguen siendo listas de strings simples
        generos = set(data.get("generos", []))
        keywords = set(data.get("keywords", []))
        personas = data.get("personas", {})
        actores = set(personas.get("actores", []))
        directores = set(personas.get("directores", []))
        
        config_nlp = data.get("configuracion_nlp", {})
        int_globales = config_nlp.get("intenciones_globales", [])
        umbral_defecto = config_nlp.get("umbral_defecto", 0.7)
        intenciones_dict = data.get("intenciones", {})
        
        return (generos, actores, directores, colecciones, estudios, 
                keywords, intenciones_dict, int_globales, umbral_defecto, plataformas)

    except Exception as e:
        print(f"Error al cargar el JSON: {e}")
        return set(), set(), set(), [], [], set(), {}, [], 0.7, []

# Carga global del sistema
(GENEROS, ACTORES, DIRECTORES, COLECCIONES, PRODUCTORAS, 
 KEYWORDS, INTENCIONES, INT_GLOBALES, UMBRAL_DEFECTO, PLATAFORMAS) = load_local_movie_data()

def analyze_intent_and_tags(text):
    """Analiza la polaridad y extrae tags contextuales."""
    text_lower = text.lower()
    tokens = re.findall(r'\b\w+\b', text_lower)
    
    tags_detectados = []
    for cat_name, info in INTENCIONES.items():
        for kw in info["keywords"]:
            kw_l = kw.lower()
            if " " in kw_l:
                if kw_l in text_lower:
                    tags_detectados.append(cat_name)
                    break
            elif kw_l in tokens:
                tags_detectados.append(cat_name)
                break

    keywords_querer = ["quiero", "gusta", "encanta", "apetece", "amo", "recomienda", "busca", "ponme", "ver"]
    keywords_negacion = ["no", "ni", "nunca", "jamás", "nada", "tampoco", "ninguna"]
    keywords_descubrir = ["nuevo", "sorprendeme", "descubrir", "estreno", "joya", "diferente"]

    tiene_querer = False
    tiene_no_querer = False
    tiene_descubrir = any(kw in tokens for kw in keywords_descubrir)

    for i, word in enumerate(tokens):
        if word in keywords_querer:
            contexto_previo = tokens[max(0, i-2):i]
            if any(neg in contexto_previo for neg in keywords_negacion):
                tiene_no_querer = True
            else:
                tiene_querer = True
        if word in ["odio", "detesto", "asco", "quita", "evita"]:
            tiene_no_querer = True

    if tiene_querer and tiene_no_querer: intencion = "CONTRADICCION"
    elif tiene_no_querer: intencion = "NO_QUERER"
    elif tiene_descubrir: intencion = "DESCUBRIR"
    elif tiene_querer: intencion = "QUERER"
    else: intencion = "QUERER"

    clean_tags = [t.replace("TAG_", "").replace("COMPAÑIA_", "").replace("ESTADO_ANIMO_", "").replace("_", " ").title() for t in tags_detectados]
    return intencion, list(set(clean_tags))

def get_genres_by_string(genres):
    with open("DB/genres.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    genres_num = []
    for genre in genres:
        for item in data['genres']:
            if genre.lower() == item['nombre'].lower():
                genres_num.append(item['id'])
    return genres_num

def get_string_by_genre(genre_num):
    with open("DB/genres.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data['genres']:
        if genre_num == item['id']:
            return item['name']

def get_movie_details(movie_id):
    url = f"{BASE_URL}/movie/{movie_id}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=keywords"
    response = requests.get(url).json()
    return response

def calcular_puntuacion(movie, profile):
    """Lógica heurística para decidir cuánto le gusta una peli al usuario."""
    details = get_movie_details(movie['id'])
    score = 0

    # Bonificación por Géneros
    movie_genre_ids = movie.get('genre_ids', [])
    for g_id in movie_genre_ids:
        # Aquí necesitarías una función inversa que mapee ID de TMDB -> Nombre
        nombre_genero = get_string_by_genre(g_id)
        score += profile['afinidad_generos'].get(nombre_genero, 0)

    # Bonificación por Década
    release = movie.get('release_date', '')
    if release:
        año = release[:4]
        decada = f"{(int(año) // 10) * 10}"
        score += profile['afinidad_decadas'].get(decada, 0) * 2  # Peso doble

    #Bonificación por tiempo de la película
    runtime = details.get('runtime', 0)
    if runtime > 0:
        diff = abs(runtime - profile['estadisticas_generales']['media_tiempo'])
        if diff < 20:
            score += 1.5

    movie_keywords = [k['name'].lower() for k in details.get('keywords', {}).get('keywords', [])]

    #Bonificación por matríz de descubrimiento
    for gen_name, factor in profile['matriz_descubrimiento'].items():
        if gen_name.lower() in movie_keywords:
            score += (factor * 2)

    return score

def load_user_profile(filepath="DB/datos_letterboxd.json"):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def search_by_genre(genres):
    genres_num = get_genres_by_string(genres)
    genres_formatted_string = ",".join(map(str, genres_num))
    search_url = f"{BASE_URL}/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&adult=false&sort_by=popularity.desc&with_genres={genres_formatted_string}"
    try:
        response = requests.get(search_url).json()
        movies = response['results']
        if not movies:
            return None

        profile = load_user_profile()

        scored_movies = []
        for movie in movies:
            score = calcular_puntuacion(movie, profile)
            scored_movies.append({
                "data": movie,
                "score": score
            })

        scored_movies.sort(key=lambda x: x['score'], reverse=True)

        top_3 = []
        for item in scored_movies[:3]:
            m = item['data']
            top_3.append({
                "title": m.get('title'),
                "score": item['score'],
                "overview": m.get('overview'),
                "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
                "release": m.get('release_date')
            })
        return top_3
    except:
        return None

def search_by_antigenre(genres):
    genres_num = get_genres_by_string(genres)
    genres_formatted_string = ",".join(map(str, genres_num))
    search_url = f"{BASE_URL}/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&adult=false&sort_by=popularity.desc&without_genres={genres_formatted_string}"
    try:
        response = requests.get(search_url).json()
        movies = response['results']
        if not movies:
            return None

        profile = load_user_profile()

        scored_movies = []
        for movie in movies:
            score = calcular_puntuacion(movie, profile)
            scored_movies.append({
                "data": movie,
                "score": score
            })

        scored_movies.sort(key=lambda x: x['score'], reverse=True)

        top_3 = []
        for item in scored_movies[:3]:
            m = item['data']
            top_3.append({
                "title": m.get('title'),
                "score": item['score'],
                "overview": m.get('overview'),
                "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
                "release": m.get('release_date')
            })
        return top_3
    except:
        return None

def get_person_id(name):
    url = f"{BASE_URL}/search/person?api_key={TMDB_API_KEY}&query={name}"
    response = requests.get(url).json()
    if response.get('results'):
        return response['results'][0]['id']
    return None


def search_by_actor_or_director(entities):
    all_people_ids = []

    #Procesar Actores
    if entities.get("actores"):
        for nombre in entities["actores"]:
            pid = get_person_id(nombre)
            if pid: all_people_ids.append(str(pid))

    #Procesar Directores
    if entities.get("directores"):
        for nombre in entities["directores"]:
            pid = get_person_id(nombre)
            if pid: all_people_ids.append(str(pid))

    #Crear el string único people_id si hay IDs recolectados
    if all_people_ids:
        #Eliminamos duplicados (por si alguien es actor y director a la vez)
        unique_people_ids = list(set(all_people_ids))
        people_id = ",".join(unique_people_ids)

    search_url = f"{BASE_URL}/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&adult=false&sort_by=popularity.desc&with_crew={people_id}"
    try:
        response = requests.get(search_url).json()
        print(response)
        movies = response['results']
        if not movies:
            return None

        profile = load_user_profile()

        scored_movies = []
        for movie in movies:
            score = calcular_puntuacion(movie, profile)
            scored_movies.append({
                "data": movie,
                "score": score
            })

        scored_movies.sort(key=lambda x: x['score'], reverse=True)

        top_3 = []
        for item in scored_movies[:3]:
            m = item['data']
            top_3.append({
                "title": m.get('title'),
                "score": item['score'],
                "overview": m.get('overview'),
                "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
                "release": m.get('release_date')
            })
        return top_3
    except:
        return None

def get_collection_id(name):
    url = f"{BASE_URL}/search/collection?api_key={TMDB_API_KEY}&query={name}&language=es-ES"
    response = requests.get(url).json()
    if response.get('results'):
        # Retornamos el ID de la primera coincidencia encontrada
        return response['results'][0]['id']
    return None

def search_by_collection(entities):
    #Procesar Sagas
    if entities.get("sagas"):
        ids_sagas = []
        for nombre in entities["sagas"]:
            cid = get_collection_id(nombre)
            if cid: ids_sagas.append(str(cid))

        if ids_sagas:
            unique_collection_ids = list(set(ids_sagas))
            collections_id = ",".join(unique_collection_ids)

    search_url = f"{BASE_URL}/collection/{collections_id}?api_key={TMDB_API_KEY}&language=es-ES"
    try:
        response = requests.get(search_url).json()
        print(response)
        movies = response['parts']
        if not movies:
            return None

        profile = load_user_profile()

        scored_movies = []
        for movie in movies:
            score = calcular_puntuacion(movie, profile)
            scored_movies.append({
                "data": movie,
                "score": score
            })

        scored_movies.sort(key=lambda x: x['score'], reverse=True)

        top_3 = []
        for item in scored_movies[:3]:
            m = item['data']
            top_3.append({
                "title": m.get('title'),
                "score": item['score'],
                "overview": m.get('overview'),
                "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
                "release": m.get('release_date')
            })
        return top_3
    except:
        return None

def search_discovery():
    """Realiza una búsqueda exploratoria sin filtros restrictivos."""
    # Buscamos películas de alta calidad (Top Tier)
    search_url = f"{BASE_URL}/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&sort_by=vote_average.desc&vote_average.gte=7.5&vote_count.gte=2000primary_release_date.gte=2025-01-01"

    response = requests.get(search_url).json()
    movies = response.get('results', [])

    if not movies:
        return None

    # Puntuamos las películas encontradas usando el perfil
    scored_movies = []
    profile = load_user_profile()
    for movie in movies:
        # Usamos tu función de scoring, que ya cruza géneros y década
        score = calcular_puntuacion(movie, profile)
        scored_movies.append({"data": movie, "score": score})

    # Ordenamos y cogemos las mejores
    scored_movies.sort(key=lambda x: x['score'], reverse=True)

    #Para "sorprender", en lugar de devolver la 1ª, elegimos al azar entre las 5 mejores
    candidates = scored_movies[:5]
    choice = random.choice(candidates)

    m = choice['data']
    return {
        "title": m.get('title'),
        "score": choice['score'],
        "overview": m.get('overview'),
        "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
        "release": m.get('release_date')
    }

def detect_entities(text_original):
    """Detecta entidades con lógica de prioridad literal y umbral dinámico[cite: 1, 2]."""
    text_lower = text_original.lower()
    doc = nlp(text_lower)
    palabras_usuario = [t.text for t in doc if len(t.text) > 2]
    lemas_usuario = [t.lemma_ for t in doc]

    res = {
        "generos": [g for g in lemas_usuario if g in GENEROS],
        "actores": [],
        "directores": [],
        "sagas": [],
        "productoras": [],
        "plataformas": [],
        "temas": []
    }

    # Definimos mapeo para iterar las listas que tienen lógica de umbral
    categorias = [
        ("sagas", COLECCIONES),
        ("plataformas", PLATAFORMAS),
        ("productoras", PRODUCTORAS)
    ]

    for clave_res, lista_datos in categorias:
        for item in lista_datos:
            # Normalización del nombre y umbral según el tipo de dato
            if isinstance(item, dict):
                nombre_entidad = item.get("nombre", "").lower()
                threshold = item.get("umbral", UMBRAL_DEFECTO)
            else:
                nombre_entidad = str(item).lower()
                threshold = UMBRAL_DEFECTO

            if not nombre_entidad: continue

            # 1. Prioridad Literal: Si el nombre está tal cual en la frase
            if nombre_entidad in text_lower:
                res[clave_res].append(nombre_entidad.title())
                continue 
            
            # 2. Respaldo Flexible: Para nombres largos con umbral bajo[cite: 1]
            if threshold < 0.5:
                palabras_clave = [w for w in nombre_entidad.split() if len(w) > 4]
                if any(w in text_lower for w in palabras_clave):
                    res[clave_res].append(nombre_entidad.title())
            
            # 3. Respaldo Fuzzy: Similitud difusa para errores ortográficos[cite: 1]
            else:
                if fuzzy_match(text_lower, nombre_entidad, threshold):
                    res[clave_res].append(nombre_entidad.title())

    # Personas (Búsqueda por palabras exactas)
    for palabra in palabras_usuario:
        for a in ACTORES:
            if palabra in a.split(): res["actores"].append(a.title())
        for d in DIRECTORES:
            if palabra in d.split(): res["directores"].append(d.title())
            
    # Temas/Keywords
    for k in KEYWORDS:
        if k in text_lower and len(k) > 4:
            res["temas"].append(k)

    # Limpieza final de duplicados
    for key in res: 
        res[key] = list(set(res[key]))
    return res

def process_text(text):
    doc = nlp(text.lower())
    return [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]

def apply_rules(words):
    try:
        with open("DB/rules.json", 'r', encoding='utf-8') as f:
            rules_list = json.load(f)
    except:
        return "Dime más sobre qué tipo de cine buscas."
    
    selected_rule = None
    for word in words:
        for rule in rules_list:
            if rule["palabra"].lower() == word:
                if selected_rule is None or rule["prioridad"] > selected_rule["prioridad"]:
                    selected_rule = rule
    return selected_rule["respuesta"] if selected_rule else "Dime más sobre qué tipo de cine buscas."

def search_movie_visual(movie_name):
    search_url = f"{BASE_URL}/search/movie?api_key={TMDB_API_KEY}&language=es-ES&query={movie_name}"
    try:
        response = requests.get(search_url).json()
        if response.get('results'):
            movie = response['results'][0]
            return {
                "title": movie.get('title'),
                "overview": movie.get('overview'),
                "poster": f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else None,
                "release": movie.get('release_date')
            }
    except: return None