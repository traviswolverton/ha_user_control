FROM python:3.11-alpine

RUN pip3 install --no-cache-dir \
    fastapi==0.111.0 \
    uvicorn==0.29.0 \
    jinja2==3.1.4 \
    "ruamel.yaml==0.18.6" \
    requests==2.31.0 \
    python-multipart==0.0.9

COPY app/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8099", "--app-dir", "/app"]
