# syntax=docker/dockerfile:1
FROM python:3.13-alpine
WORKDIR /code
RUN pip install poetry
COPY poetry.lock pyproject.toml /code
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_NO_INTERACTION=1
RUN poetry install --no-interaction --no-ansi --no-root
EXPOSE 5683
COPY . .
CMD ["python3", "-m", "outpost.serve"]