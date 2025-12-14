import os
import asyncio
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Numeric, DateTime, Text, select, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration - reads from environment variables
DB_USER = os.getenv("DB_USER", "jordans_db")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "local-postgres-rw")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "happy_pancakes")

# Construct database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

logger.info(f"Connecting to database at {DB_HOST}:{DB_PORT}/{DB_NAME}")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define the Pancake model
class Pancake(Base):
    __tablename__ = "pancakes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    fluffiness_level = Column(Integer, nullable=True)
    syrup_type = Column(String(100), nullable=True)
    is_buttery = Column(Boolean, default=True)
    magical_factor = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    taste_notes = Column(Text, nullable=True)

# Pydantic models for API requests/responses
class PancakeCreate(BaseModel):
    name: str
    fluffiness_level: int | None = None
    syrup_type: str | None = None
    is_buttery: bool = True
    magical_factor: float | None = None
    taste_notes: str | None = None

class PancakeResponse(BaseModel):
    id: int
    name: str
    fluffiness_level: int | None
    syrup_type: str | None
    is_buttery: bool
    magical_factor: float | None
    created_at: datetime
    taste_notes: str | None
    
    class Config:
        from_attributes = True

# FastAPI app
app = FastAPI(title="Pancake Backend", description="A magical pancake database service")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    logger.info("Starting up Pancake Backend service...")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connection successful!")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "pancake-backend"}

@app.get("/")
async def serve_index():
    """Serve the frontend"""
    import pathlib
    index_path = pathlib.Path(__file__).parent.parent / "python_pg_ui" / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Welcome to Pancake Palace!"}

@app.get("/api/pancakes", response_model=list[PancakeResponse])
async def get_all_pancakes(db: Session = Depends(get_db)):
    """Get all pancakes"""
    pancakes = db.query(Pancake).all()
    return pancakes

@app.post("/api/pancakes", response_model=PancakeResponse)
async def create_pancake(pancake: PancakeCreate, db: Session = Depends(get_db)):
    """Create a new pancake"""
    db_pancake = Pancake(**pancake.dict())
    db.add(db_pancake)
    db.commit()
    db.refresh(db_pancake)
    return db_pancake

# Serve static files
import pathlib
static_dir = pathlib.Path(__file__).parent.parent / "python_pg_ui" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
