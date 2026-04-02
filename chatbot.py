import nltk
import json
import spacy
from nltk.stem import SnowballStemmer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

#Para cargar si no existe
nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True) # Recomendado añadirlo también por si usas word_tokenize

nlp = spacy.load("es_core_news_sm")
stemmer = SnowballStemmer("spanish")
STOPWORDS_ES = set(stopwords.words('spanish'))

def process_text(text):
    doc = nlp(text.lower())
 
    tokens = [
        token for token in doc
        if token.is_alpha                        # solo letras (sin números ni puntuación)
        and not token.is_stop                    # sin stopwords según spacy
        and token.text not in STOPWORDS_ES       # sin stopwords según nltk (doble filtro)
        and len(token.text) > 2                  # descartar palabras de 1-2 letras
    ]
 
    # Lematización: "películas" → "película", "quiero" → "querer"
    return [token.lemma_ for token in tokens]

def apply_rules(words):
    with open("DB/rules.json", 'r', encoding='utf-8') as f:
        rules_list = json.load(f)

    selected_rule = None

    for word in words:
        # Pasamos la palabra del usuario a minúsculas para comparar
        word_lower = word.lower() 
        
        for rule in rules_list:
            # Comparamos la palabra del JSON con la del usuario
            if rule["palabra"].lower() == word_lower:
                # Lógica de prioridad
                if selected_rule is None or rule["prioridad"] > selected_rule["prioridad"]:
                    selected_rule = rule

    if selected_rule:
        return selected_rule["respuesta"]
    else:
        return "Lo siento, no tengo información sobre eso. Intenta con otra palabra."

def chatbot():
    print("Chatbot iniciado. Escribe 'salir' para terminar.")
    while True:
        s = input("Usuario> ")
        
        if s.lower() in ["salir", "exit", "adiós"]:
            print("¡Hasta la vista!")
            break

        important_words = process_text(s)

        print("Palabras importantes:", important_words)

        # Ejecutar reglas
        result = apply_rules(important_words)
        print("Jordi'sFilming>", result)

# Ejecutar el chatbot
if __name__ == "__main__":
    chatbot()