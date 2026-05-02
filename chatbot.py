import re
import json
import spacy
import requests 
from nltk.corpus import stopwords
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