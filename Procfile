# Procfile — for use with honcho, foreman, or Heroku-style runners
# Install honcho:  pip install honcho
# Run all:         honcho start
# Run one:         honcho start query

query:     gunicorn app.query_api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
ingestion: gunicorn app.ingestion_api:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001 --access-logfile - --error-logfile -
