"""PhotoShare REST API entry point."""
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.conf.config import settings
from src.database.db import get_db
from src.routes import auth, comments, photos, ratings, users

DESCRIPTION = """
**PhotoShare** — REST API for sharing photos.

* JWT authentication (access + refresh tokens, logout with a token blacklist)
* Roles: user, moderator, administrator (the first registered user is the administrator)
* Photos in Cloudinary with up to 5 tags, transformations, links and QR codes
* Comments, ratings, search and filtering

Authorize with the **Authorize** button: put your email or username and password.
"""

app = FastAPI(title="PhotoShare", version="1.0.0", description=DESCRIPTION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, users, photos, comments, ratings):
    app.include_router(module.router, prefix="/api")
app.include_router(photos.links_router, prefix="/api")


@app.get("/", tags=["health"], summary="Welcome")
def root():
    return {"message": "PhotoShare API", "docs": "/docs"}


@app.get("/api/healthchecker", tags=["health"], summary="Check the database connection")
def healthchecker(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not available")
    return {"message": "OK"}
