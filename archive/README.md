# Archived scaffold

The old Django project that lived inside `frontend/` is preserved in `legacy-django/`.
It is not imported by the active app. Its database is preserved and ignored by Git.

Use `backend/manage.py` and the root Python 3.12 `.venv` for the current backend.
The older `backend/.venv` is left untouched for rollback/reference, but should not be used with the updated requirements.
