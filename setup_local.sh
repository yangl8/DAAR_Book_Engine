#!/usr/bin/env bash

# Script d’installation automatique pour DAAR Book Engine.
# Lancer depuis la racine du dépôt :
#   bash setup_local.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
LIB_DIR="$ROOT_DIR/library"
DB_PATH="$LIB_DIR/db_index.sqlite3"
DB_URL="https://github.com/yangl8/DAAR_Book_Engine/releases/download/v1/db_index.sqlite3"

command -v python3 >/dev/null 2>&1 || {
  echo "python3 est requis mais introuvable." >&2
  exit 1
}

PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info[0])")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info[1])")

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
  echo "Python 3.10 ou supérieur est requis (version détectée : $PYTHON_VERSION)." >&2
  echo "Installez une version plus récente (ex. python3.10 ou python3.11) puis relancez le script." >&2
  exit 1
fi

command -v curl >/dev/null 2>&1 || {
  echo "curl est requis pour télécharger la base d'index." >&2
  exit 1
}

PYTHON_BIN="python3"
# Préférence pour python3.10/p3.11 si disponibles explicitement
for candidate in python3.11 python3.10; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done

echo "Création/actualisation de l'environnement virtuel avec $PYTHON_BIN..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Version de Python utilisée : $(python -V)"

echo "Mise à jour de pip..."
pip install --upgrade pip >/dev/null

echo "Installation des dépendances Python..."
pip install -r "$LIB_DIR/requirements.txt"

echo "Application des migrations Django..."
python "$LIB_DIR/manage.py" migrate

echo "Téléchargement systématique de la dernière base d'index..."
rm -f "$DB_PATH"
curl -L -o "$DB_PATH" "$DB_URL"

echo
echo "Installation terminée."
echo "Activez l'environnement avec :"
echo "  source venv/bin/activate"
echo "Puis lancez le serveur :"
echo "  cd library && python manage.py runserver"

