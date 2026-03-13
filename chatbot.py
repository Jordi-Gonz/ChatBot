import nltk
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
import tkinter as tk

lemmatizer = WordNetLemmatizer()


def apply_rules(words):
    # Dictionary of rules
    rules = {
        'hola': 'Hola. En qué puedo ayudarte?',
        'miedo': 'Una buena película de miedo es \'It\'.',
        'adiós': 'Adiós!'
    }

    # Check nouns in dictionary
    for word in words:
        try:
            return rules[word]
        except:
            None


def chatbot():
    while True:
        s = input("Usuario: ")
        
        # Tokenization
        words = nltk.word_tokenize(s.lower(), language='spanish')
        if s.lower() == "exit" or s.lower() == "adiós":
            print("Adiós!")
            break

        # Run rules with extracted words
        result = apply_rules(words)
        print(result)

chatbot()