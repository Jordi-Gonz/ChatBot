import re
import json
import spacy
import requests 
import random
import unicodedata
from difflib import SequenceMatcher

# Configuración TMDB
TMDB_API_KEY = "8fdeff49fbf33e98768b3eaaf592bb59" 
BASE_URL = "https://api.themoviedb.org/3"

# Carga de recursos NLP
nlp = spacy.load("es_core_news_sm")

def fuzzy_match(text, target, threshold):
    """Calcula la similitud entre dos textos."""
    return SequenceMatcher(None, text, target).ratio() >= threshold

def normalize_for_keyword_match(text):
    """Normaliza texto para detectar keywords en español sin problemas de acentos o signos."""
    text = str(text).lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9ñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_exact_keyword_phrase(text_norm, phrase_norm):
    """Busca una palabra/frase completa evitando matches parciales."""
    if not phrase_norm:
        return False

    pattern = r"(?<!\w)" + re.escape(phrase_norm) + r"(?!\w)"
    return re.search(pattern, text_norm) is not None


def load_keyword_translation_map(filepath="DB/keyword_map_es.json"):
    """Carga el diccionario español -> keyword real de TMDB/API.

    Formato esperado:
    [
        {"palabra": "supervivencia", "palabra_api": "survival"},
        {"palabra": "viajes en el tiempo", "palabra_api": "time travel"}
    ]
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Aviso: no existe {filepath}. Se seguirá sin diccionario ES->API.")
        return []
    except Exception as e:
        print(f"Error al cargar {filepath}: {e}")
        return []

    resultado = []

    for item in data:
        if not isinstance(item, dict):
            continue

        palabra = item.get("palabra", "")
        palabra_api = item.get("palabra_api", "")

        if not palabra or not palabra_api:
            continue

        resultado.append({
            "palabra": palabra,
            "palabra_norm": normalize_for_keyword_match(palabra),
            "palabra_api": palabra_api
        })

    resultado.sort(key=lambda x: len(x["palabra_norm"]), reverse=True)

    return resultado


def detect_translated_keywords_with_ranges(text_original):
    """Detecta keywords españolas y devuelve (keywords_api, rangos_ocupados).

    Los rangos sirven para que después no se añadan keywords inglesas más genéricas
    que estén dentro de la frase ya detectada.
    """
    text_norm = normalize_for_keyword_match(text_original)
    detectadas = []
    rangos_ocupados = []

    for item in KEYWORD_MAP_ES:
        palabra_norm = item["palabra_norm"]

        if not palabra_norm:
            continue

        pattern = r"(?<!\w)" + re.escape(palabra_norm) + r"(?!\w)"
        match = re.search(pattern, text_norm)

        if not match:
            continue

        inicio, fin = match.span()

        # Si esta keyword está dentro de otra más larga ya detectada, la saltamos.
        solapa = any(not (fin <= ini_ocupado or inicio >= fin_ocupado)
                     for ini_ocupado, fin_ocupado in rangos_ocupados)

        if solapa:
            continue

        detectadas.append(item["palabra_api"])
        rangos_ocupados.append((inicio, fin))

    return list(dict.fromkeys(detectadas)), rangos_ocupados


def detect_translated_keywords(text_original):
    """Detecta keywords escritas en español y devuelve la keyword real en inglés de TMDB."""
    detectadas, _ = detect_translated_keywords_with_ranges(text_original)
    return detectadas

def normalize_for_match(text):
    """Normaliza texto para comparar entidades sin problemas de mayúsculas, acentos o signos."""
    text = str(text).lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9ñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize_for_match(text):
    """Devuelve tokens normalizados útiles para comparar nombres de personas."""
    return re.findall(r"\b[a-z0-9ñ]+\b", normalize_for_match(text))


def contains_exact_phrase(text_norm, phrase_norm):
    """Comprueba una frase completa con límites de palabra para evitar matches tipo Tom -> Tom Holland."""
    if not phrase_norm:
        return False
    pattern = r"(?<!\w)" + re.escape(phrase_norm) + r"(?!\w)"
    return re.search(pattern, text_norm) is not None


STOP_WORDS_PERSONA = {
    "de", "del", "la", "las", "los", "da", "das", "do", "dos",
    "van", "von", "bin", "ibn", "jr", "sr", "ii", "iii"
}

PALABRAS_CONTEXTO_PERSONA = {
    "con", "de", "del", "por", "para", "sobre", "en", "y", "o",
    "actor", "actriz", "director", "directora", "reparto", "protagonista",
    "peli", "pelicula", "películas", "peliculas", "quiero", "busco",
    "recomienda", "recomiendame", "ponme", "ver", "algo"
}


def split_person_name(nombre):
    """Separa una persona en nombre y apellidos/partes importantes."""
    tokens = tokenize_for_match(nombre)
    importantes = [t for t in tokens if t not in STOP_WORDS_PERSONA]

    if not importantes:
        importantes = tokens

    nombre_principal = importantes[0] if importantes else ""
    apellidos = importantes[1:] if len(importantes) > 1 else []

    return {
        "original": str(nombre),
        "tokens": tokens,
        "importantes": importantes,
        "nombre": nombre_principal,
        "apellidos": apellidos,
        "frase": " ".join(tokens)
    }


def apellido_contexto_valido(text_tokens_ordenados, apellido, info):
    """Comprueba si un apellido detectado aparece en un contexto razonable.

    Si justo antes del apellido hay otro nombre propio que no pertenece
    a esa persona, se considera falso positivo.
    """
    indices = [i for i, tok in enumerate(text_tokens_ordenados) if tok == apellido]

    if not indices:
        return False

    tokens_persona = info["tokens"]
    importantes_persona = info["importantes"]

    try:
        pos_apellido_en_persona = tokens_persona.index(apellido)
        tokens_antes_apellido = tokens_persona[:pos_apellido_en_persona]
    except ValueError:
        tokens_antes_apellido = []

    inmediato_anterior_persona = tokens_antes_apellido[-1] if tokens_antes_apellido else ""

    iniciales_colapsadas = "".join(
        t for t in tokens_antes_apellido
        if t not in STOP_WORDS_PERSONA and len(t) <= 2
    )

    for idx in indices:
        if idx == 0:
            return True

        anterior = text_tokens_ordenados[idx - 1]

        # Caso normal
        if anterior in PALABRAS_CONTEXTO_PERSONA or anterior in STOP_WORDS_PERSONA:
            return True

        # Caso nombre completo real o apellidos compuestos
        if inmediato_anterior_persona and anterior == inmediato_anterior_persona:
            return True

        # Permite que el usuario omita una inicial intermedia
        if (
            info["nombre"]
            and len(info["nombre"]) > 1
            and anterior == info["nombre"]
            and all(t in STOP_WORDS_PERSONA or len(t) <= 2 for t in tokens_antes_apellido[1:])
        ):
            return True

        # Caso iniciales escritas juntas
        if iniciales_colapsadas and anterior == iniciales_colapsadas:
            return True

    return False


def score_person_match(text_norm, text_tokens, nombre_persona):
    """Puntúa cuánto encaja un actor/director con el texto del usuario.

    Pesos:
    - Nombre completo exacto: 100.
    - Nombre + apellido: 95.
    - Apellido: 70, pero solo si el contexto no contradice el nombre.
    - Apellido extra: +15.
    - Solo nombre propio: 25, por debajo del mínimo.
    """
    info = split_person_name(nombre_persona)

    if not info["tokens"]:
        return 0

    # Nombres artísticos de una sola palabra
    if len(info["importantes"]) == 1:
        return 100 if contains_exact_phrase(text_norm, info["frase"]) else 0

    # Nombre completo exacto
    if contains_exact_phrase(text_norm, info["frase"]):
        return 100

    score = 0
    nombre_match = info["nombre"] in text_tokens if info["nombre"] else False
    apellidos_match = [
        ap for ap in info["apellidos"]
        if ap in text_tokens and ap not in STOP_WORDS_PERSONA and len(ap) > 1
    ]

    if nombre_match:
        score += 25

    if apellidos_match:
        text_tokens_ordenados = list(text_tokens) if not isinstance(text_tokens, set) else []

        if not text_tokens_ordenados:
            text_tokens_ordenados = tokenize_for_match(text_norm)

        apellidos_validos = [
            ap for ap in apellidos_match
            if apellido_contexto_valido(text_tokens_ordenados, ap, info)
        ]

        if not apellidos_validos:
            apellidos_match = []
        else:
            apellidos_match = apellidos_validos
            score += 70
            if len(apellidos_match) > 1:
                score += 15 * (len(apellidos_match) - 1)

    if nombre_match and apellidos_match:
        score += 25

    return min(score, 100)


def detect_people_by_weight(text_original, personas, min_score=70):
    """Detecta actores/directores usando pesos por nombre y apellidos.
    """
    text_norm = normalize_for_match(text_original)
    text_tokens = tokenize_for_match(text_original)
    detectados = []

    for persona in personas:
        score = score_person_match(text_norm, text_tokens, persona)
        if score >= min_score:
            detectados.append((str(persona).title(), score))

    # Ordenamos por confianza y quitamos duplicados manteniendo el mejor score.
    mejor_por_nombre = {}
    for nombre, score in detectados:
        if nombre not in mejor_por_nombre or score > mejor_por_nombre[nombre]:
            mejor_por_nombre[nombre] = score

    return [nombre for nombre, _ in sorted(mejor_por_nombre.items(), key=lambda x: x[1], reverse=True)]

def load_local_movie_data(filepath="DB/movie_dataset.json"):
    """Carga todas las entidades, etiquetas e intenciones configuradas."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Estas listas contienen objetos/diccionarios según tu JSON
        estudios = data.get("estudios", [])
        plataformas = data.get("plataformas", []) 
        generos = set(data.get("generos", []))
        keywords = set(data.get("keywords", []))
        personas = data.get("personas", {})
        actores = set(personas.get("actores", []))
        directores = set(personas.get("directores", []))
        
        config_nlp = data.get("configuracion_nlp", {})
        int_globales = config_nlp.get("intenciones_globales", [])
        umbral_defecto = config_nlp.get("umbral_defecto", 0.7)
        intenciones_dict = data.get("intenciones", {})
        
        return (generos, actores, directores, estudios, 
                keywords, intenciones_dict, int_globales, umbral_defecto, plataformas)

    except Exception as e:
        print(f"Error al cargar el JSON: {e}")
        return set(), set(), set(), [], [], set(), {}, [], 0.7, []

# Carga global del sistema
(GENEROS, ACTORES, DIRECTORES, ESTUDIOS, 
 KEYWORDS, INTENCIONES, INT_GLOBALES, UMBRAL_DEFECTO, PLATAFORMAS) = load_local_movie_data()
# Traducción keywords
KEYWORD_MAP_ES = load_keyword_translation_map()
# Relación entre tags contextuales y filtros reales de búsqueda.
TAG_TO_ENTITIES = {
    "Familiar": {
        "generos": ["familia"],
        "temas": []
    },
    "Pareja": {
        "generos": ["romance"],
        "temas": []
    },
    "Animo Pos": {
        "generos": ["comedia"],
        "temas": []
    },
    "Animo Neg": {
        "generos": ["drama"],
        "temas": []
    },
    "Nostalgia": {
        "generos": [],
        "temas": ["nostalgia"]
    }
}

def apply_tags_to_entities(entities, tags):
   
    if not entities:
        entities = {}

    for key in ["generos", "actores", "directores", "estudios", "plataformas", "temas"]:
        entities.setdefault(key, [])

    for tag in tags:
        extra = TAG_TO_ENTITIES.get(tag)
        if not extra:
            continue

        for key, valores in extra.items():
            entities.setdefault(key, [])
            for valor in valores:
                if valor not in entities[key]:
                    entities[key].append(valor)

    for key in entities:
        entities[key] = list(dict.fromkeys(entities[key]))

    return entities


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
    """Obtiene el ID de persona en TMDB priorizando coincidencia exacta de nombre."""
    url = f"{BASE_URL}/search/person?api_key={TMDB_API_KEY}&query={name}"
    response = requests.get(url).json()
    results = response.get('results', [])

    if not results:
        return None

    name_norm = normalize_for_match(name)
    for person in results:
        if normalize_for_match(person.get('name', '')) == name_norm:
            return person.get('id')

    return results[0].get('id')

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
    """Detecta entidades con match más seguro."""
    text_lower = text_original.lower()
    doc = nlp(text_lower)
    lemas_usuario = [t.lemma_ for t in doc]

    res = {
        "generos": [g for g in lemas_usuario if g in GENEROS],
        "actores": [],
        "directores": [],
        "estudios": [],
        "plataformas": [],
        "temas": []
    }

    categorias = [
        ("plataformas", PLATAFORMAS),
        ("estudios", ESTUDIOS)
    ]

    STOP_WORDS_ENTIDADES = {"studio", "studios", "pictures", "films", "entertainment", "productions", "cine", "cinema"}

    for clave_res, lista_datos in categorias:
        for item in lista_datos:
            if isinstance(item, dict):
                nombre_entidad = item.get("nombre", "").lower()
                threshold = item.get("umbral", UMBRAL_DEFECTO)
            else:
                nombre_entidad = str(item).lower()
                threshold = UMBRAL_DEFECTO

            if not nombre_entidad:
                continue

            tokens_usuario = re.findall(r"\b\w+\b", text_lower)

            if nombre_entidad in text_lower:
                if len(nombre_entidad) <= 3 and nombre_entidad not in tokens_usuario:
                    continue
                res[clave_res].append(nombre_entidad.title())
                continue

            palabras_entidad = [w for w in nombre_entidad.split() if w not in STOP_WORDS_ENTIDADES]
            
            if not palabras_entidad:
                continue
                
            match_detectado = False
            for token in tokens_usuario:
                if len(token) <= 3 and threshold > 0.5:
                    if token == nombre_entidad:
                        match_detectado = True
                        break
                    continue
                
                if fuzzy_match(token, palabras_entidad[0], threshold):
                    match_detectado = True
                    break
            
            if match_detectado:
                res[clave_res].append(nombre_entidad.title())

    # Personas: actores/directores con pesos por nombre y apellidos.
    res["actores"] = detect_people_by_weight(text_original, ACTORES)
    res["directores"] = detect_people_by_weight(text_original, DIRECTORES)

  # Temas/Keywords en español traducidas a la keyword real de TMDB.
    translated_keywords, rangos_ocupados_keywords = detect_translated_keywords_with_ranges(text_original)
    for keyword_api in translated_keywords:
        res["temas"].append(keyword_api)

    # Temas/Keywords ya escritas como aparecen en la API.
    text_norm_keywords = normalize_for_keyword_match(text_original)

    keywords_ordenadas = sorted(
        KEYWORDS,
        key=lambda kw: len(normalize_for_keyword_match(kw)),
        reverse=True
    )

    for k in keywords_ordenadas:
        k_norm = normalize_for_keyword_match(k)

        if not k_norm:
            continue

        pattern = r"(?<!\w)" + re.escape(k_norm) + r"(?!\w)"
        match = re.search(pattern, text_norm_keywords)

        if not match:
            continue

        inicio, fin = match.span()
        solapa = any(
            not (fin <= ini_ocupado or inicio >= fin_ocupado)
            for ini_ocupado, fin_ocupado in rangos_ocupados_keywords
        )

        if solapa:
            continue

        res["temas"].append(k)
        rangos_ocupados_keywords.append((inicio, fin))

    for key in res:
        res[key] = list(dict.fromkeys(res[key]))

    return res

def process_text(text):
    doc = nlp(text.lower())
    return [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]

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

    search_url = f"{BASE_URL}/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&adult=false"

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

    profile = load_user_profile()
    decadas_a_filtrar = []

    if entities.get("decada"):
        decadas_a_filtrar.append(int(entities["decada"]))
    else:
        afinidad_decadas = profile.get('afinidad_decadas', {})
        decadas_top = sorted(afinidad_decadas.items(), key=lambda x: x[1], reverse=True)[:3]
        decadas_a_filtrar = [int(dec[0]) for dec in decadas_top if dec[0].isdigit()]

    if decadas_a_filtrar:
        año_minimo = min(decadas_a_filtrar)
        año_maximo = max(decadas_a_filtrar) + 9
        search_url += f"&primary_release_date.gte={año_minimo}-01-01&primary_release_date.lte={año_maximo}-12-31"
        
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