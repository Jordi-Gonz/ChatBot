import nltk
import json
import spacy
import requests # Necesitas instalarlo: pip install requests
from nltk.corpus import stopwords

# Configuración TMDB
TMDB_API_KEY = "8fdeff49fbf33e98768b3eaaf592bb59" 
BASE_URL = "https://api.themoviedb.org/3"

# Carga de recursos NLP
nlp = spacy.load("es_core_news_sm")
STOPWORDS_ES = set(stopwords.words('spanish'))

def search_movie_visual(movie_name):
    """Busca una película en TMDB para obtener su poster y detalles."""
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
    except Exception as e:
        print(f"Error en búsqueda visual: {e}")
    return None

def fetch_tmdb_data():
    generos = set()
    actores = set()
    directores = set()

    try:
        gen_url = f"{BASE_URL}/genre/movie/list?api_key={TMDB_API_KEY}&language=es-ES"
        gen_data = requests.get(gen_url).json()
        for g in gen_data.get('genres', []):
            name_lower = g['name'].lower()
            generos.add(name_lower)
            doc = nlp(name_lower)
            generos.add(doc[0].lemma_)

        for page in range(1, 41): 
            per_url = f"{BASE_URL}/person/popular?api_key={TMDB_API_KEY}&language=es-ES&page={page}"
            per_data = requests.get(per_url).json()
            
            for p in per_data.get('results', []):
                name = p['name'].lower()
                dept = p.get('known_for_department')
                
                if dept == 'Directing':
                    directores.add(name)
                elif dept == 'Acting':
                    actores.add(name)

        with open("DB/generos.json", "w", encoding="utf-8") as f:
            json.dump(list(generos), f, ensure_ascii=False, indent=4)
        
        with open("DB/personas.json", "w", encoding="utf-8") as f:
            json.dump({
                "actores": list(actores),
                "directores": list(directores)
            }, f, ensure_ascii=False, indent=4)
            
        print(f"¡Éxito! Ahora tienes {len(directores)} directores en tu base de datos.")

    except Exception as e:
        print(f"Error: {e}")
    
    return generos, actores, directores

# Cargamos los datos globales
GENEROS, ACTORES, DIRECTORES = fetch_tmdb_data()

def process_text(text):
    doc = nlp(text.lower())
    # Importante: devolvemos lemas
    return [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]

def apply_rules(words):
    # Intentamos abrir el archivo local para las respuestas personalizadas
    try:
        with open("DB/rules.json", 'r', encoding='utf-8') as f:
            rules_list = json.load(f)
    except:
        return "No tengo reglas configuradas, pero detecto que te interesa el cine."

    selected_rule = None
    for word in words:
        for rule in rules_list:
            if rule["palabra"].lower() == word:
                if selected_rule is None or rule["prioridad"] > selected_rule["prioridad"]:
                    selected_rule = rule
    
    return selected_rule["respuesta"] if selected_rule else "Dime más sobre qué tipo de cine buscas."

def detect_entities(important_words):
    # Comprobamos tanto lemas (para géneros) como el texto original (para nombres)
    return {
        "generos": [w for w in important_words if w in GENEROS],
        "actores": [w for w in important_words if w in ACTORES],
        "directores": [w for w in important_words if w in DIRECTORES]
    }