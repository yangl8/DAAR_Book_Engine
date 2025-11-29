- Accès en ligne : https://daar-book-engine.onrender.com/
  - Hébergement gratuit, première ouverture possible après ~2 minutes (démarrage du serveur).
  - Pour travailler confortablement, privilégiez l’exécution locale (bien plus rapide).

# DAAR Book Engine

DAAR Book Engine est une application Django de recherche plein texte et de recommandation bâtie sur un corpus Project Gutenberg nettoyé. Elle combine index TF‑IDF, moteur regex, graphe de similarité et scores de centralité pour proposer des résultats pertinents.

## Fonctionnalités principales
- Recherche par mots-clés (TF‑IDF normalisé + pondération par centralité)
- Recherche ciblée par titre, auteur ou expressions régulières
- Recommandations de livres similaires à partir d’un graphe de documents
- Scripts de construction de l’index (nettoyage, tokenisation, calcul TF‑IDF, graphe)

## Architecture en bref
- **Framework** : Django 4.2 (`library/`)
- **Base d’index** : SQLite (`db_index.sqlite3`) contenant tables `books`, `terms`, `postings`, `document_graph`, `document_scores`
- **Front-end** : templates Django + `static/css/main.css` et `static/js/search.js`
- **Commandes personnalisées** : disponibles dans `library/corpus/management/commands/`

## Prérequis
- Python ≥ 3.10 (3.11 recommandé) — les dépendances (Django 5.2, click 8.3, etc.) ne sont pas compatibles avec Python 3.9.
- `git`, `pip`, `curl` (ou navigateur) pour récupérer les ressources

## Installation locale
### Option rapide (script automatisé)
- Depuis la racine du dépôt :
  ```bash
  bash setup_local.sh
  ```
- Le script crée l’environnement virtuel, installe les dépendances, applique les migrations et télécharge systématiquement la dernière base d’index (en remplaçant la précédente le cas échéant).
- Une fois terminé :
  ```bash
  source venv/bin/activate
  cd library
  python manage.py runserver
  ```

### Étapes manuelles
1. Cloner le dépôt :
   ```bash
   git clone https://github.com/yangl8/DAAR_Book_Engine.git
   cd DAAR_Book_Engine
   ```
2. Créer et activer un environnement virtuel :
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # macOS / Linux
   # Sous Windows :
   # venv\Scripts\activate
   ```
3. Installer les dépendances :
   ```bash
   cd library
   pip install -r requirements.txt
   ```
   > Si vous avez déjà exécuté `setup_local.sh`, il suffit d'activer l'environnement existant : `source ../venv/bin/activate`.
4. Appliquer les migrations Django (admin/auth) :
   ```bash
   python manage.py migrate
   ```

## Récupérer la base d’index
Le fichier généré est trop volumineux pour Git : téléchargez-le avant de lancer le serveur.
```bash
curl -L -o db_index.sqlite3 https://github.com/yangl8/DAAR_Book_Engine/releases/download/v1/db_index.sqlite3
```
Placez-le dans `library/`. Sans ce fichier, les requêtes `/api/search` échoueront (`no such table: terms`).
En cas d'échec de téléchargement, vérifiez votre connexion réseau et la taille du fichier obtenu (`ls -lh db_index.sqlite3`).

### Régénérer l’index (optionnel)
```bash
cd library
./index_full_build.sh
```
Ce script :
1. (Re)migre la base d’index
2. Nettoie les textes, tokenise, applique TF‑IDF Top‑K
3. Calcule DF, centralités et graphe de similarité

## Lancement et scripts utiles
- Démarrer le serveur de développement :
  ```bash
  python manage.py runserver
  ```
  Accès local : http://127.0.0.1:8000/
- Vérification rapide : 
  ```bash
  curl http://127.0.0.1:8000/api/index/stats
  ```
  (devrait retourner un JSON contenant `documents`, `terms`, etc.)

- Vérifier les statistiques d’index (CSV dans `library/test/`) :
  ```bash
  python manage.py export_index_stats
  ```

- Recalculer uniquement le TF‑IDF :
  ```bash
  python manage.py index_compute_tfidf
  ```

## Ressources code
- Téléchargement & nettoyage du corpus : `download_and_filter_gutenberg_html.py`
- Moteur de recherche : `library/corpus/backend/search_service.py`
- API & vues Django : `library/corpus/views.py`
- Recommandations : `library/corpus/backend/recommendations.py`
- Endpoints REST principaux : `/api/search`, `/api/recommendations/query`, `/api/index/stats`