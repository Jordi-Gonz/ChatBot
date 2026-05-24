import cloudscraper
from bs4 import BeautifulSoup
import re
import pandas as pd
import json
import time

scraper = cloudscraper.create_scraper()

GENRES = ['Action', 'Adventure', 'Animation', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Family', 'Fantasy', 'History', 'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction', 'Thriller', 'TV Movie', 'War', 'Western']
YEARS = [2020, 2010, 2000, 1990, 1980, 1970, 1960, 1950, 1940, 1930, 1920, 1910, 1900, 1890, 1880, 1870]

lista_vistas = []

import cloudscraper
from bs4 import BeautifulSoup
import re
import pandas as pd
import json
import time
from concurrent.futures import ThreadPoolExecutor  # <-- La clave de la velocidad

scraper = cloudscraper.create_scraper()

GENRES = ['Action', 'Adventure', 'Animation', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Family', 'Fantasy', 'History', 'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction', 'Thriller', 'TV Movie', 'War', 'Western']
YEARS = [2020, 2010, 2000, 1990, 1980, 1970, 1960, 1950, 1940, 1930, 1920, 1910, 1900, 1890, 1880, 1870]

lista_vistas = []

def procesar_pelicula(p):
    """
    Función independiente para procesar una sola película. 
    Se ejecutará en paralelo para maximizar la velocidad.
    """
    try:
        pelicula = {}

        img = p.find('img')
        titulo = img['alt'] if img else "Sin título"
        
        rating_span = p.find('span', class_='rating')
        if rating_span:
            clases = rating_span.get('class')
            valor_clase = [c for c in clases if 'rated-' in c][0]
            num_rating = int(valor_clase.split('-')[1])
            estrellas = num_rating / 2
        else:
            estrellas = None

        pelicula['title'] = titulo
        pelicula['rating'] = estrellas
        
        link = p.find('div', class_='react-component')['data-item-link']

        url_members = 'https://letterboxd.com' + link + '/members'
        resp_members = scraper.get(url_members)
        if resp_members.status_code == 200:
            soup_m = BeautifulSoup(resp_members.text, 'html.parser')
            try:
                pelicula['vistas'] = int(soup_m.find('li', class_='js-route-watches').find('a').get('title').replace(',', '').split()[0])
            except:
                pelicula['vistas'] = 0
        else:
            pelicula['vistas'] = 0

        url_peli = 'https://letterboxd.com' + link
        resp_peli = scraper.get(url_peli)
        if resp_peli.status_code == 200:
            soup_p = BeautifulSoup(resp_peli.text, 'html.parser')

            datos_json_tag = soup_p.find('script', type='application/ld+json')
            if datos_json_tag and datos_json_tag.string:
                try:
                    text = datos_json_tag.string.split('/* <![CDATA[ */')[1].split('/* ]]> */')[0].strip()
                    info = json.loads(text)
                    pelicula['global-rating'] = float(info.get('aggregateRating').get('ratingValue'))
                    
                    generos = info.get('genre')
                    pelicula['genres'] = [generos] if isinstance(generos, str) else generos
                except:
                    pelicula['global-rating'] = 0.0
                    pelicula['genres'] = []
            else:
                pelicula['global-rating'] = 0.0
                pelicula['genres'] = []

            try:
                pelicula['year'] = int(soup_p.find('span', class_='releasedate').get_text())
            except:
                pelicula['year'] = 0

            try:
                pelicula['time'] = int(soup_p.find('p', class_='text-link text-footer').get_text().split(' ')[1].split()[0])
            except:
                pelicula['time'] = 0

            return pelicula

    except Exception as e:
        print(f"Error procesando una película: {e}")
    return None


def obtener_lista(usuario):
    global lista_vistas
    url_base = f"https://letterboxd.com/{usuario}/films/"
    
    todas_las_peliculas_html = []
    num_pagina = 1

    url_actual = 1
    
    while url_actual:
        try:
            if num_pagina == 1:
                respuesta = scraper.get(url_base)
            else:
                respuesta = scraper.get(url_base + f"page/{num_pagina}/")

            if respuesta.status_code != 200:
                print(f"Error al acceder a la página {num_pagina}: {respuesta.status_code}")
                break
                
            soup = BeautifulSoup(respuesta.text, 'html.parser')
            peliculas_pagina = soup.find_all('li', class_='griditem')
            
            if not peliculas_pagina:
                break
                
            todas_las_peliculas_html.extend(peliculas_pagina)
            
            boton_siguiente = soup.find('a', class_='next')
            if boton_siguiente:
                num_pagina += 1
                time.sleep(1)
            else:
                url_actual = 0
                
        except Exception as e:
            print(f"Error recopilando la lista de páginas: {e}")
            break

    total_items = len(todas_las_peliculas_html)
    if total_items == 0:
        print("No se encontraron películas en el perfil de este usuario.")
        return

    with ThreadPoolExecutor(max_workers=4) as executor:
        resultados = executor.map(procesar_pelicula, todas_las_peliculas_html)
        
    lista_vistas = [r for r in resultados]

usuario = 'reimonlef'
inicio = time.time()
obtener_lista(usuario)
fin = time.time()

print(fin - inicio)

genre_data = []

for item in GENRES:
    total = 0
    total_rating = 0
    rating = 0
    global_rating = 0
    genre = {}
    for p in lista_vistas:
        if item in p['genres']:
            total += 1
            if p['rating'] is not None:
                total_rating += 1
                rating += p['rating']
            
            global_rating += p['global-rating']

    if total == 0:
        genre = {
            'genre': item,
            'total': total,
            'total_rating': total_rating,
            'rating': 0,
            'global-rating': 0
        }
    else:
        if total_rating == 0:
            genre = {
                'genre': item,
                'total': total,
                'total-rating': total_rating,
                'rating': 0,
                'global-rating': round(global_rating / total, 3)
            }
        else:
            genre = {
                'genre': item,
                'total': total,
                'total-rating': total_rating,
                'rating': round(rating / total_rating, 3),
                'global-rating': round(global_rating / total, 3)
            }

    genre_data.append(genre)

decade_data = []

for item in YEARS:
    total = 0
    total_rating = 0
    rating = 0
    global_rating = 0
    decade = {}
    for p in lista_vistas:
        if p['year'] >= item and p['year'] < item + 10:
            total += 1
            if p['rating'] is not None:
                total_rating += 1
                rating += p['rating']
            global_rating += p['global-rating']

    if total == 0:
        decade = {
            'decade': item,
            'total': total,
            'total-rating': total_rating,
            'rating': 0,
            'global-rating': 0
        }
    else:
        if total_rating == 0:
            decade = {
                'decade': item,
                'total': total,
                'rating': 0,
                'global-rating': round(global_rating / total, 3)
            }
        else:
            decade = {
                'decade': item,
                'total': total,
                'rating': round(rating / total_rating, 3),
                'global-rating': round(global_rating / total, 3)
            }

    decade_data.append(decade)

df = pd.DataFrame(lista_vistas)

media_time = df['time'].mean()
media_global = df['global-rating'].mean()
media_vistas = df['vistas'].mean()

df_genre = pd.DataFrame(genre_data)
df_year = pd.DataFrame(decade_data)

max_vistas_genre = df_genre['total'].max() if df_genre['total'].max() > 0 else 1
max_rating_genre = df_genre['rating'].max() if df_genre['rating'].max() > 0 else 1
max_vistas_year = df_year['total'].max() if df_year['total'].max() > 0 else 1
max_rating_year = df_year['rating'].max() if df_year['rating'].max() > 0 else 1

genre_afinidad = {}
year_afinidad = {}
matriz_descubrir = {}

for d in genre_data:
    if d['rating'] == 0 and d['total'] > 0:
        score_nota = 0.5 
    else:
        score_nota = d['rating'] / max_rating_genre

    score = (score_nota * 0.7) + (d['total'] / max_vistas_genre * 0.3)
    genre_afinidad[d['genre']] = float(round(score, 3))

    factor_novedad = 1 - (d['total'] / max_vistas_genre)
    
    interes_potencial = d['global-rating'] / 5.0
    
    score_descubrimiento = (factor_novedad * 0.8) + (interes_potencial * 0.2)
    matriz_descubrir[d['genre']] = float(round(score_descubrimiento, 3))

for d in decade_data:
    if d['rating'] == 0 and d['total'] > 0:
        score_nota = 0.5
    else:
        score_nota = d['rating'] / max_rating_year

    score = (score_nota * 0.7) + (d['total'] / max_vistas_year * 0.3)
    year_afinidad[d['decade']] = float(round(score, 3))

resultados_finales = {
    "usuario": usuario,
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

print("Los datos se han guardado exitosamente en 'datos_letterboxd.json'")
