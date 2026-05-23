import cloudscraper
from bs4 import BeautifulSoup
import re
import pandas as pd
import json 

scraper = cloudscraper.create_scraper()

GENRES = ['Action', 'Adventure', 'Animation', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Family', 'Fantasy', 'History', 'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction', 'Thriller', 'TV Movie', 'War', 'Western']
YEARS = [2020, 2010, 2000, 1990, 1980, 1970, 1960, 1950, 1940, 1930, 1920, 1910, 1900, 1890, 1880, 1870]

lista_vistas = []

def obtener_lista(usuario):
    url = f"https://letterboxd.com/{usuario}/films/"
    
    try:
        respuesta = scraper.get(url)
        
        if respuesta.status_code == 200:
            soup = BeautifulSoup(respuesta.text, 'html.parser')

            peliculas = soup.find_all('li', class_='griditem')
            
            if not peliculas:
                return
            
            for p in peliculas:
                pelicula = {}

                img = p.find('img')
                titulo = img['alt']
                
                rating_span = p.find('span', class_=re.compile(r'rated-(\d+)'))
                
                if rating_span:
                    clases = rating_span.get('class')
                    valor_clase = [c for c in clases if 'rated-' in c][0]
                    num_rating = int(valor_clase.split('-')[1])
                    
                    estrellas = num_rating / 2
                else:
                    estrellas = None

                pelicula['title'] = titulo
                pelicula['rating'] = estrellas
                
                link = p.find('div', class_ = 'react-component')['data-item-link']

                url = 'https://letterboxd.com/csi' + link + 'rating-histogram/'

                respuesta = scraper.get(url)
            
                if respuesta.status_code == 200:
                    soup = BeautifulSoup(respuesta.text, 'html.parser')

                    pelicula['global-rating'] = float(soup.find('a', class_= 'averagerating').get_text())

                url = 'https://letterboxd.com/csi' + link + 'stats/'
    
                respuesta = scraper.get(url)
            
                if respuesta.status_code == 200:
                    soup = BeautifulSoup(respuesta.text, 'html.parser')
                    pelicula['vistas'] = int(soup.find('div', class_='-watches').get('aria-label').split()[2].replace(',', ''))

                url = 'https://letterboxd.com' + link
        
                respuesta = scraper.get(url)
                
                if respuesta.status_code == 200:
                    soup = BeautifulSoup(respuesta.text, 'html.parser')

                    pelicula['year'] = int(soup.find('span', class_='releasedate').get_text())

                    pelicula['time'] = int(soup.find('p', class_='text-link text-footer').get_text().split(' ')[1].split()[0])

                    genres_list = []

                    genres = soup.find('div', id='tab-panel-genres').find('div', class_='text-sluglist').find_all('a')

                    for item in genres:
                        genres_list.append(item.get_text())

                    pelicula['genres'] = genres_list
            
                lista_vistas.append(pelicula)
            
    except Exception as e:
        print(f"Ocurrió un error: {e}")

obtener_lista('Jordigg')

genre_data = []

for item in GENRES:
    total = 0
    rating = 0
    global_rating = 0
    genre = {}
    for p in lista_vistas:
        if item in p['genres']:
            total += 1
            rating += p['rating']
            global_rating += p['global-rating']

    if total == 0:
        genre = {
            'genre': item,
            'total': total,
            'rating': 0,
            'global-rating': 0
        }
    else:
        genre = {
            'genre': item,
            'total': total,
            'rating': round(rating / total, 3),
            'global-rating': round(global_rating / total, 3)
        }

    genre_data.append(genre)

decade_data = []

for item in YEARS:
    total = 0
    rating = 0
    global_rating = 0
    decade = {}
    for p in lista_vistas:
        if p['year'] >= item and p['year'] < item + 10:
            total += 1
            rating += p['rating']
            global_rating += p['global-rating']

    if total == 0:
        decade = {
            'decade': item,
            'total': total,
            'rating': 0,
            'global-rating': 0
        }
    else:
        decade = {
            'decade': item,
            'total': total,
            'rating': round(rating / total, 3),
            'global-rating': round(global_rating / total, 3)
        }

    decade_data.append(decade)

df = pd.DataFrame(lista_vistas)
print(df.columns)

media_time = 0#df['time'].mean()
media_global = 0#df['global-rating'].mean()
media_vistas = 0#df['vistas'].mean()

df_genre = pd.DataFrame(genre_data)
df_year = pd.DataFrame(decade_data)

max_vistas_genre = df_genre['total'].max()
max_rating_genre = df_genre['rating'].max()
max_vistas_year = df_year['total'].max()
max_rating_year = df_year['rating'].max()

genre_afinidad = {}
year_afinidad = {}
matriz_descubrir = {}

for d in genre_data:
    score = (d['rating'] / max_rating_genre * 0.7) + (d['total'] / max_vistas_genre * 0.3)
    genre_afinidad[d['genre']] = float(round(score, 3))

    factor_novedad = 1 - (d['total'] / max_vistas_genre)
    interes_potencial = d['rating'] / max_rating_genre
    score_descubrimiento = (factor_novedad * 0.8) + (interes_potencial * 0.2)
    matriz_descubrir[d['genre']] = float(round(score_descubrimiento, 3))

for d in decade_data:
    score = (d['rating'] / max_rating_year * 0.7) + (d['total'] / max_vistas_year * 0.3)
    year_afinidad[d['decade']] = float(round(score, 3))

resultados_finales = {
    "usuario": "Jordigg",
    "estadisticas_generales": {
        "media_tiempo": media_time,
        "media_global": media_global,
        "media_vistas": media_vistas
    },
    "afinidad_generos": genre_afinidad,
    "afinidad_decadas": year_afinidad,
    "matriz_descubrimiento": matriz_descubrir
}

# Guardamos en un archivo JSON
with open('DB/datos_letterboxd.json', 'w', encoding='utf-8') as f:
    json.dump(resultados_finales, f, indent=4, ensure_ascii=False)

print("\nLos datos se han guardado exitosamente en 'datos_letterboxd.json'")
