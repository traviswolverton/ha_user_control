FROM python:3.11-slim

RUN pip3 install --no-cache-dir \
    fastapi==0.110.3 \
    uvicorn==0.29.0 \
    jinja2==3.1.4 \
    pyyaml \
    requests==2.31.0 \
    python-multipart==0.0.9

COPY app/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8099", "--app-dir", "/app"]
