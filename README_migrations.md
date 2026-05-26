Alembic migrations
==================

This project uses SQLModel for models. Alembic is configured to use `SQLModel.metadata`.

Quick start
-----------

1. Install dependencies:

```powershell
cd "c:\Users\moham\OneDrive\Desktop\FocusSpark\FocusSpark-Backend"
python -m pip install -r requirements.txt
```

2. Ensure `DATABASE_URL` is set in your environment or in a `.env` file. Example:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://user:pass@localhost/dbname"
$env:JWT_SECRET = "change_me"
```

3. Create an initial migration (autogenerate):

```powershell
alembic revision --autogenerate -m "initial"
```

4. Apply migrations:

```powershell
alembic upgrade head
```

Notes
-----
- The app currently calls `SQLModel.metadata.create_all(engine)` in `app/db/database.py` on startup. For production, remove or guard that call and rely on Alembic migrations instead.
- If models are in separate modules, ensure they are imported in `alembic/env.py` (see the import block) so `target_metadata` includes them for autogenerate.
- Use `alembic revision --autogenerate` to capture schema changes, review generated scripts, then `alembic upgrade` to apply.
