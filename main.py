
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import RedirectResponse
from datetime import datetime
from schemas import ShortenRequest, ShortenResponse, MetadataResponse
import string, random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from db import SessionLocal, engine
from models import ShortURL

app = FastAPI(title="URL Shortener Service", description="A production-ready REST API for shortening URLs.")

SHORT_CODE_LENGTH = 6
ALPHABET = string.ascii_letters + string.digits

async def generate_short_code(session: AsyncSession, length=SHORT_CODE_LENGTH) -> str:
    while True:
        code = ''.join(random.choices(ALPHABET, k=length))
        result = await session.execute(select(ShortURL).where(ShortURL.code == code))
        if not result.scalar():
            return code

async def get_db():
    async with SessionLocal() as session:
        yield session

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(ShortURL.metadata.create_all)


async def create_short_url(req: ShortenRequest, db: AsyncSession, retry_times: int = 1):
    code = req.custom_alias
    now = datetime.utcnow()
    if code:
        # Check if custom alias exists
        result = await db.execute(select(ShortURL).where(ShortURL.code == code))
        if result.scalar():
            raise HTTPException(status_code=409, detail="Short code already exists.")
        short_url = ShortURL(code=code, url=str(req.url), created_at=now, hits=0)
        db.add(short_url)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="Short code already exists.")
        return ShortenResponse(code=code, url=req.url, created_at=now)
    # Auto-generate code with retry
    for attempt in range(retry_times + 1):
        code = await generate_short_code(db)
        short_url = ShortURL(code=code, url=str(req.url), created_at=now, hits=0)
        db.add(short_url)
        try:
            await db.commit()
            return ShortenResponse(code=code, url=req.url, created_at=now)
        except IntegrityError:
            await db.rollback()
            if attempt == retry_times:
                raise HTTPException(status_code=409, detail="Short code already exists after retry.")

@app.post("/shorten", response_model=ShortenResponse)
async def shorten_url(req: ShortenRequest, db: AsyncSession = Depends(get_db)):
    return await create_short_url(req, db, retry_times=1)

@app.get("/{code}")
async def redirect(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ShortURL).where(ShortURL.code == code))
    entry = result.scalar()
    if not entry:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    entry.hits += 1
    await db.commit()
    return RedirectResponse(entry.url)

@app.get("/meta/{code}", response_model=MetadataResponse)
async def get_metadata(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ShortURL).where(ShortURL.code == code))
    entry = result.scalar()
    if not entry:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    return MetadataResponse(code=code, url=entry.url, created_at=entry.created_at, hits=entry.hits)
