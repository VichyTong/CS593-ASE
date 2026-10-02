FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py database.py pdf_tools.py providers.py ./
COPY templates ./templates
COPY static ./static
RUN useradd --create-home researcher && mkdir /app/data && chown researcher:researcher /app/data
USER researcher
ENV DATA_DIR=/app/data
EXPOSE 8000
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--timeout", "180", "--bind", "0.0.0.0:8000", "app:create_app()"]
