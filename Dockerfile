FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LIBREOFFICE_PYTHON=/usr/bin/python3

# Dépendances système :
# - Python système
# - SQLite
# - LibreOffice Calc
# - PyUNO
# - outils nécessaires à uv / installation
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	python3 \
	python3-pip \
	python3-venv \
	python3-dev \
	python3-uno \
	sqlite3 \
	libreoffice-calc \
	libreoffice-script-provider-python \
	curl \
	ca-certificates \
	build-essential \
	&& rm -rf /var/lib/apt/lists/*

# Installation de uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copie d'abord les fichiers de dépendances
# pour profiter du cache Docker
COPY pyproject.toml uv.lock ./

# Création de l'environnement du projet
RUN uv sync --frozen --no-install-project

# Copie du reste du projet
COPY . .

# Installation du projet lui-même
RUN uv sync --frozen

# Répertoires de travail
RUN mkdir -p \
	/data/sources \
	/data/output \
	/data/work

# Par défaut, ton programme principal
ENTRYPOINT ["uv", "run", "traitement"]