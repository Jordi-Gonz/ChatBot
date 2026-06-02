# 🍿 Jordi's Filming

Recomendador inteligente de películas con interfaz conversacional en español. Analiza tus preferencias a partir de tu historial de Letterboxd y utiliza la API de TMDB para sugerirte películas personalizadas.

---

## ✨ Características

- **Análisis de intención** — detecta si quieres buscar, descartar o descubrir películas a partir de lenguaje natural
- **Extracción de entidades** — identifica géneros, actores, directores, productoras, plataformas y temas en el mensaje del usuario
- **Perfil de usuario** — importa y procesa el historial de Letterboxd para calcular afinidades por género y década
- **Sistema de blacklist** — permite excluir de forma permanente géneros, actores, directores, estudios o temas
- **Scoring personalizado** — puntúa cada película cruzando los resultados de TMDB con el perfil del usuario
- **Modo descubrimiento** — cuando el usuario quiere sorprenderse, sugiere películas de alta valoración fuera de su zona de confort
- **Interfaz Streamlit** — chat visual con tarjetas de película (póster, descripción, fecha de estreno)

---

## 🗂️ Estructura del proyecto

```
├── app.py                  # Punto de entrada
├── window.py               # Interfaz Streamlit (chat + sidebar)
├── chatbot.py              # Lógica NLP: detección de entidades, intenciones y búsqueda en TMDB
├── data.py                 # Scraping de Letterboxd y generación del perfil de usuario
└── DB/
    ├── datos_letterboxd.json   # Perfil del usuario (afinidades, blacklist, estadísticas)
    ├── movie_dataset.json      # Entidades configurables: géneros, actores, directores, estudios, keywords...
    ├── keyword_map_es.json     # Diccionario español → keyword real de TMDB
    └── genres.json             # Tabla de géneros TMDB (id, nombre en inglés y español)
```

---

## 🚀 Instalación

### Requisitos

- Python 3.9+
- Cuenta gratuita en [TMDB](https://www.themoviedb.org/) para obtener una API Key

### Pasos

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd <carpeta>

# 2. Instalar dependencias
pip install streamlit spacy cloudscraper beautifulsoup4 pandas requests

# 3. Descargar el modelo de spaCy en español
python -m spacy download es_core_news_sm

# 4. Iniciar la aplicación
streamlit run app.py
```

---

## 🛠️ Uso

### Configurar usuario de Letterboxd (opcional)

En el **sidebar** de la aplicación, introduce tu nombre de usuario de Letterboxd y pulsa *Guardar Usuario*. La aplicación hará scraping de tu historial y generará tu perfil de afinidades automáticamente. Si no tienes cuenta, se usará un perfil de invitado.

### Ejemplos de consultas

| Mensaje | Comportamiento |
|---|---|
| `Quiero una peli de acción con Tom Hanks` | Busca acción + Tom Hanks en TMDB |
| `No quiero más terror` | Añade "Terror" a la blacklist |
| `Sorpréndeme` | Modo descubrimiento: película de alta valoración |
| `Estoy con mis hijos y nos gusta Disney` | Detecta tag *Familiar* y filtra por género Familia/Disney |
| `Algo de los 80 con Spielberg` | Filtra por década y director |

### Intenciones detectadas

| Icono | Intención | Significado |
|---|---|---|
| ✅ | `QUERER` | El usuario busca activamente algo |
| ❌ | `NO_QUERER` | El usuario quiere excluir algo |
| ✨ | `DESCUBRIR` | El usuario quiere una sorpresa |
| 🤨 | `CONTRADICCIÓN` | El mensaje contiene señales opuestas |

---

## ⚙️ Configuración avanzada

### `DB/movie_dataset.json`

Define las entidades reconocibles por el chatbot:

- `generos` — lista de géneros en español
- `personas.actores` / `personas.directores` — nombres que el sistema puede detectar en los mensajes
- `estudios` / `plataformas` — objetos con `nombre` y `umbral` de similitud fuzzy
- `keywords` — temas/palabras clave en inglés para TMDB
- `intenciones` — tags contextuales (Familiar, Pareja, Ánimo positivo/negativo, Nostalgia...) con sus keywords en español
- `configuracion_nlp.umbral_defecto` — umbral de similitud fuzzy global (por defecto `0.7`)

### `DB/datos_letterboxd.json`

Es el perfil del usuario. Se genera automáticamente al introducir un usuario de Letterboxd (o se inicializa vacío para el modo invitado) y se actualiza en tiempo real cuando el usuario usa el chatbot.

```json
{
  "usuario": "nombre_de_usuario",
  "estadisticas_generales": {
    "media_tiempo": 112.4,
    "media_global": 3.6,
    "media_vistas": 85000
  },
  "afinidad_generos": {
    "Action": 0.85,
    "Drama": 0.72,
    "Comedy": 0.0,
    ...
  },
  "afinidad_decadas": {
    "2020": 0.9,
    "1990": 0.65,
    ...
  },
  "matriz_descubrimiento": {
    "Documentary": 0.88,
    "Western": 0.76,
    ...
  },
  "blacklist": {
    "generos": ["Terror"],
    "actores": [],
    "directores": [],
    "estudios": [],
    "temas": []
  }
}
```

Cada campo en detalle:

- **`estadisticas_generales`** — medias globales del historial: duración media de las películas vistas, nota media global y media de vistas en Letterboxd. Se usan para ajustar el scoring (por ejemplo, se bonifica una película cuya duración esté a menos de 20 minutos de la media del usuario).
- **`afinidad_generos`** — puntuación entre `0.0` y `1.0` para cada género, calculada combinando la nota media que el usuario ha dado a ese género (70%) y la cantidad de películas vistas de ese género (30%).
- **`afinidad_decadas`** — misma lógica que `afinidad_generos` pero agrupando las películas por década de estreno. Se usa para filtrar automáticamente los resultados de TMDB por las décadas preferidas del usuario cuando no especifica ninguna.
- **`matriz_descubrimiento`** — puntuación de "cuánto le queda por explorar" en cada género. Se calcula invirtiendo la afinidad (géneros poco vistos con buena valoración global salen primero) para sugerir contenido fuera de la zona de confort.
- **`blacklist`** — listas de exclusión permanente. Cuando el usuario dice *"no quiero más terror"* o *"nunca más Shyamalan"*, se añaden aquí y el scoring penaliza fuertemente cualquier película que los contenga.

---

### `DB/genres.json`

Tabla de traducción entre los IDs numéricos de géneros de TMDB y sus nombres en inglés y español. La API de TMDB trabaja internamente con IDs (por ejemplo, `28` para Acción), por lo que este archivo actúa como puente entre lo que escribe el usuario en español y los filtros que se envían a la API.

```json
{
  "genres": [
    { "id": 28,    "name": "Action",         "nombre": "Acción" },
    { "id": 35,    "name": "Comedy",         "nombre": "Comedia" },
    { "id": 878,   "name": "Science Fiction","nombre": "Ciencia Ficción" },
    ...
  ]
}
```

Cuando el usuario escribe *"quiero una de ciencia ficción"*, el chatbot busca `"ciencia ficción"` en el campo `nombre` de este archivo, obtiene el `id` correspondiente (`878`) y lo incluye en la llamada a `/discover/movie` de TMDB. Del mismo modo, cuando se muestra información de una película al usuario, se usa `name` (inglés) para cruzar datos con el perfil, que también almacena los géneros en inglés.

---

### `DB/keyword_map_es.json`

Diccionario para traducir términos en español a keywords de TMDB:

```json
[
  { "palabra": "viajes en el tiempo", "palabra_api": "time travel" },
  { "palabra": "supervivencia", "palabra_api": "survival" }
]
```

---

## 📦 Dependencias principales

| Librería | Uso |
|---|---|
| `streamlit` | Interfaz web del chat |
| `spaCy` + `es_core_news_sm` | NLP en español (lematización) |
| `requests` | Llamadas a la API de TMDB |
| `cloudscraper` + `beautifulsoup4` | Scraping de Letterboxd |
| `pandas` | Procesamiento del historial de usuario |

---

## 📝 Notas

- El scraping de Letterboxd puede tardar varios minutos dependiendo del tamaño del historial.
- La API Key de TMDB tiene un límite de peticiones por segundo; con listas muy grandes podría ser necesario añadir delays.
- El perfil del usuario se guarda localmente en `DB/datos_letterboxd.json` y persiste entre sesiones.