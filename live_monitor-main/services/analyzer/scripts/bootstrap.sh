if [ -d /app/minio_api ]; then
  if [ -f /app/minio_api/requirements.txt ]; then
    pip install --no-cache-dir -r /app/minio_api/requirements.txt
  fi
  if [ -f /app/minio_api/pyproject.toml ] || [ -f /app/minio_api/setup.py ] || [ -f /app/minio_api/setup.cfg ]; then
    pip install --no-cache-dir /app/minio_api
  fi
fi