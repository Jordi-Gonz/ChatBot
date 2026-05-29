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
(GENEROS, ACTORES, DIRECTORES, COLECCIONES, ESTUDIOS, 
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
    keywords_contradiccion = ["pero", "sino"]
    keywords_descubrir = ["nuevo", "sorprendeme", "descubrir", "estreno", "joya", "diferente"]

    tiene_querer = False
    tiene_no_querer = False
    tiene_contradiccion = any(kw in tokens for kw in keywords_contradiccion)
    tiene_descubrir = any(kw in tokens for kw in keywords_descubrir)

    for i, word in enumerate(tokens):
        if word in keywords_querer:
            contexto_previo = tokens[max(0, i-2):i]
            if any(neg in contexto_previo for neg in keywords_negacion):
                tiene_no_querer = True
            else:
                tiene_querer = True
        if word in ["odio", "detesto", "asco", "quita", "evita"] or word in keywords_negacion:
            tiene_no_querer = True

    if tiene_querer and tiene_no_querer or tiene_contradiccion: intencion = "CONTRADICCION"
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
            if genre.lower() in item['nombre'].lower():
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
    """Lógica heurística unificada para decidir cuánto le gusta una peli al usuario,
    calculando bonificaciones y penalizaciones de géneros en un solo bucle.
    """
    details = get_movie_details(movie['id'])
    score = 0
    
    blacklist = profile.get("blacklist", {})
    blacklist_generos = get_genres_by_string(blacklist.get("generos", []))
    blacklist_temas = [t.lower() for t in blacklist.get("temas", [])]
    blacklist_actores = [a.lower() for a in blacklist.get("actores", [])]
    blacklist_directores = [d.lower() for d in blacklist.get("directores", [])]
    
    movie_genre_ids = movie.get('genre_ids', [])
    movie_keywords = [k['name'].lower() for k in details.get('keywords', {}).get('keywords', [])]

    for g_id in blacklist_generos:
        if g_id in movie_genre_ids:
            score -= 100

    for g_id in movie_genre_ids:
        nombre_genero = get_string_by_genre(g_id)
        score += profile['afinidad_generos'].get(nombre_genero, 0)

    for kw in movie_keywords:
        if kw in blacklist_temas:
            score -= 50

    if blacklist_actores or blacklist_directores:
        try:
            credits_url = f"{BASE_URL}/movie/{movie['id']}/credits?api_key={TMDB_API_KEY}"
            credits = requests.get(credits_url).json()
            
            cast_names = [member['name'].lower() for member in credits.get('cast', [])]
            if any(actor in cast_names for actor in blacklist_actores):
                score -= 150
                
            crew_directors = [member['name'].lower() for member in credits.get('crew', []) if member.get('job') == 'Director']
            if any(director in crew_directors for director in blacklist_directores):
                score -= 150
        except Exception as e:
            pass

    release = movie.get('release_date', '')
    if release:
        año = release[:4]
        decada = f"{(int(año) // 10) * 10}"
        score += profile['afinidad_decadas'].get(decada, 0) * 2

    runtime = details.get('runtime', 0)
    if runtime > 0:
        diff = abs(runtime - profile['estadisticas_generales']['media_tiempo'])
        if diff < 20:
            score += 1.5

    return score

def load_user_profile(filepath="DB/datos_letterboxd.json"):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_person_id(name):
    url = f"{BASE_URL}/search/person?api_key={TMDB_API_KEY}&query={name}"
    response = requests.get(url).json()
    if response.get('results'):
        return response['results'][0]['id']
    return None

def save_user_profile(profile, filepath="DB/datos_letterboxd.json"):
    """Guarda el objeto perfil de usuario actualizado en el archivo JSON."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # indent=4 mantiene el archivo legible para humanos
            json.dump(profile, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error al guardar el archivo de perfil: {e}")

def registrar_en_blacklist(entities):
    """Inserta de forma permanente las entidades detectadas en la lista negra del JSON."""
    profile = load_user_profile()
    
    if "blacklist" not in profile:
        profile["blacklist"] = {
            "generos": [],
            "actores": [],
            "directores": [],
            "estudios": [],
            "temas": []
        }
        
    blacklist = profile["blacklist"]
    
    for clave_entidad, valores in entities.items():
        if clave_entidad in blacklist and valores:
            elementos_actuales = {elem.lower() for elem in blacklist[clave_entidad]}
            
            for item in valores:
                if item.lower() not in elementos_actuales:
                    blacklist[clave_entidad].append(item)
                    
    save_user_profile(profile)

def get_collection_id(name):
    url = f"{BASE_URL}/search/collection?api_key={TMDB_API_KEY}&query={name}&language=es-ES"
    response = requests.get(url).json()
    if response.get('results'):
        # Retornamos el ID de la primera coincidencia encontrada
        return response['results'][0]['id']
    return None

def get_company_id(name):
    url = f"{BASE_URL}/search/company?api_key={TMDB_API_KEY}&query={name}"
    response = requests.get(url).json()
    if response.get('results'):
        return response['results'][0]['id']
    return None

def get_provider_id(name, region="ES"):
    # Obtenemos todos los proveedores de la región
    url = f"{BASE_URL}/watch/providers/movie?api_key={TMDB_API_KEY}&watch_region={region}"
    response = requests.get(url).json()
    for p in response.get('results', []):
        if name.lower() in p['provider_name'].lower():
            return p['provider_id']
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

    top_3 = []
    m = choice['data']
    top_3.append({
        "title": m.get('title'),
        "score": choice['score'],
        "overview": m.get('overview'),
        "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
        "release": m.get('release_date')
    })
    return top_3

def detect_entities(text_original):
    """Detecta entidades con lógica de prioridad literal, palabras clave clave y umbral dinámico."""
    text_lower = text_original.lower()
    doc = nlp(text_lower)
    palabras_usuario = [t.text for t in doc if len(t.text) > 2]
    lemas_usuario = [t.lemma_ for t in doc]

    res = {
        "generos": [g for g in lemas_usuario if g in GENEROS],
        "actores": [],
        "directores": [],
        "estudios": [],
        "plataformas": [],
        "temas": []
    }

    # Definimos mapeo para iterar las listas que tienen lógica de umbral
    categorias = [
        ("plataformas", PLATAFORMAS),
        ("estudios", ESTUDIOS)
    ]

    # Palabras irrelevantes que no deben activar una búsqueda por sí solas
    STOP_WORDS_ENTIDADES = {"studio", "studios", "pictures", "films", "entertainment", "productions", "cine", "cinema"}

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

            if nombre_entidad in text_lower:
                res[clave_res].append(nombre_entidad.title())
                continue 
            
            palabras_entidad = nombre_entidad.split()
            if len(palabras_entidad) > 1:
                palabras_significativas = [w for w in palabras_entidad if w not in STOP_WORDS_ENTIDADES and len(w) > 3]
                
                if any(w in text_lower for w in palabras_significativas):
                    res[clave_res].append(nombre_entidad.title())
                    continue

            # 2. Respaldo Flexible: Para nombres largos con umbral bajo
            if threshold < 0.5:
                palabras_clave = [w for w in nombre_entidad.split() if len(w) > 4]
                if any(w in text_lower for w in palabras_clave):
                    res[clave_res].append(nombre_entidad.title())
                    continue
            
            # 3. Respaldo Fuzzy: Similitud difusa para errores ortográficos
            else:
                if fuzzy_match(text_lower, nombre_entidad, threshold):
                    res[clave_res].append(nombre_entidad.title())

    for a in ACTORES:
        if a.lower() in text_lower:
            res["actores"].append(a.title())
    for d in DIRECTORES:
        if d.lower() in text_lower:
            res["directores"].append(d.title())
            
    # Temas/Keywords
    for k in KEYWORDS:
        k_lower = k.lower()
        if k_lower in text_lower:
            res["temas"].append(k)
        elif len(k_lower.split()) > 1:
            palabras_clave_db = [w for w in k_lower.split() if len(w) > 4 or w == "dc"]
            if any(w in text_lower for w in palabras_clave_db):
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

def get_keyword_ids(keywords_list):
    """Busca en TMDB los IDs correspondientes a una lista de strings de palabras clave."""
    keyword_ids = []
    for kw in keywords_list:
        url = f"{BASE_URL}/search/keyword?api_key={TMDB_API_KEY}&query={kw}"
        try:
            response = requests.get(url).json()
            if response.get('results'):
                # Tomamos el primer resultado que coincida con la búsqueda
                keyword_ids.append(str(response['results'][0]['id']))
        except Exception as e:
            print(f"Error al buscar la keyword '{kw}': {e}")
    return keyword_ids


def get_movie_details(movie_id):
    url = f"{BASE_URL}/movie/{movie_id}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=keywords"
    response = requests.get(url).json()
    return response

def search_by_all_entities(entities, intencion="QUERER"):
    """
    Construye una búsqueda combinando dinámicamente todas las entidades detectadas.
    Soporta inclusión (QUERER) y exclusión (NO_QUERER) de entidades.
    """

    if intencion == "DESCUBRIR" and not any(entities.values()):
        return search_discovery()

    search_url = f"{BASE_URL}/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&adult=false&sort_by=popularity.desc"

    if entities.get("generos"):
        genres_num = get_genres_by_string(entities["generos"])
        if genres_num:
            genres_str = ','.join(map(str, genres_num))
            search_url += f"&with_genres={genres_str}"

    all_people_ids = []
    for grupo in ["actores", "directores"]:
        if entities.get(grupo):
            for nombre in entities[grupo]:
                pid = get_person_id(nombre)
                if pid: 
                    all_people_ids.append(str(pid))
    
    if all_people_ids:
        unique_people = list(set(all_people_ids))
        search_url += f"&with_people={','.join(unique_people)}"

    if entities.get("estudios"):
        company_ids = []
        for nombre in entities["estudios"]:
            cid = get_company_id(nombre)
            if cid: 
                company_ids.append(str(cid))
        if company_ids:
            company_str = ','.join(company_ids)
            search_url += f"&with_companies={company_str}"

    if entities.get("temas"):
        kw_ids = get_keyword_ids(entities["temas"])
        if kw_ids:
            kw_str = ','.join(kw_ids)
            search_url += f"&with_keywords={kw_str}"

    if entities.get("plataformas"):
        platform_ids = []
        for nombre in entities["plataformas"]:
            pid = get_provider_id(nombre)
            if pid: 
                platform_ids.append(str(pid))
        if platform_ids:
            search_url += f"&watch_region=ES&with_watch_providers={','.join(platform_ids)}"

    try:
        response = requests.get(search_url).json()
        movies = response.get('results', [])
        
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
                "poster": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}" if m.get('poster_path') else None,
                "release": m.get('release_date')
            })
        return top_3

    except Exception as e:
        print(f"Error en la búsqueda combinada: {e}")
        return None