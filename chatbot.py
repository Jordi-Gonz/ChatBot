import nltk
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
import tkinter as tk

lemmatizer = WordNetLemmatizer()


# Show scoring rules
def show(nouns):
    # Dictionary of scoring rules
    rules = {
        'hello': 'Hello. How can I help you?',
        'horror': 'One good horror film is \'It\'.',
        'goodbye': 'Goodbye'
    }

    # Check nouns in dictionary
    for noun in nouns:
        try:
            return rules[noun]  # Print scoring rule
        except:
            None                # Ignore if noun not found


def apply_rules(wh_words, verbs_lemm, nouns):

    return show(nouns)

def chatbot():
    while True:
        s = input("\nAsk a question about a sport (type 'exit' to quit): ")
        
        # Tokenization
        words = nltk.word_tokenize(s.lower())
        if s.lower() == "exit":
            print("Goodbye!")
            break

        # POS Tagging
        tags = nltk.pos_tag(words)
        nouns = [token for token, pos in tags if pos.startswith('N')]
        verbs = [token for token, pos in tags if pos.startswith('V')]
        adverbs = [token for token, pos in tags if pos.startswith('W')]

        verbs_lemm = []
        for verb in verbs:
            verbs_lemm.append(lemmatizer.lemmatize(verb, pos="v"))

        # Run rules with extracted words
        result = apply_rules(adverbs, verbs_lemm, nouns)
        print(result)

chatbot()