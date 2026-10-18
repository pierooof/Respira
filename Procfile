web: flask --app wsgi db upgrade && flask --app wsgi seed && gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --access-logfile -
worker: python -m worker.main
