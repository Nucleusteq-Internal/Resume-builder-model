FROM python:3.10-slim

EXPOSE 8000

WORKDIR /app
COPY requirements.txt /app
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt --no-cache-dir
COPY . /app

CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" ]