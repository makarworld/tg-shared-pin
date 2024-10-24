FROM python:3.10-slim as base

LABEL maintainer="Make t.me/abuztrade"

# Сборка зависимостей
ARG BUILD_DEPS="curl libpq-dev gcc"
RUN apt-get update && apt-get install -y $BUILD_DEPS

# Инициализация проекта
WORKDIR /app
ENTRYPOINT ["python", "main.py"]

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Установка питонячьих библиотек
RUN pip3 install --upgrade pip
COPY ./requirements.txt .
RUN pip3 install --root-user-action=ignore -r requirements.txt

# Копирование в контейнер папок и файлов.
COPY . .