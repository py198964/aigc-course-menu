FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_HOST=0.0.0.0 APP_PORT=8765 COURSE_DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 course && mkdir /data && chown course:course /data
COPY --chown=course:course . .
USER course
EXPOSE 8765
CMD ["python", "run.py"]
