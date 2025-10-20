from datetime import datetime
from sqlalchemy import (Column, Integer, Float, String, ForeignKey, DateTime)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Base = declarative_base()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Sample(Base):
    __tablename__ = "samples"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    cpu_count = Column(Integer)
    gpu_count = Column(Integer)

    cpus = relationship("CPUUsage", back_populates="sample", cascade="all, delete-orphan")
    gpus = relationship("GPUUsage", back_populates="sample", cascade="all, delete-orphan")
    disk = relationship("DiskUsage", back_populates="sample", uselist=False, cascade="all, delete-orphan")
    memory = relationship("MemoryUsage", back_populates="sample", uselist=False, cascade="all, delete-orphan")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# CPU Metrics
class CPUUsage(Base):
    __tablename__ = "cpu_usage"

    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey("samples.id", ondelete="CASCADE"), index=True)
    cpu_index = Column(Integer)
    usage_percent = Column(Float)

    sample = relationship("Sample", back_populates="cpus")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GPU Metrics
class GPUUsage(Base):
    __tablename__ = "gpu_usage"

    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey("samples.id", ondelete="CASCADE"), index=True)
    gpu_index = Column(Integer)
    usage_percent = Column(Float)
    memory_used_mb = Column(Float)
    memory_total_mb = Column(Float)

    sample = relationship("Sample", back_populates="gpus")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Disk Metrics
class DiskUsage(Base):
    __tablename__ = "disk_usage"

    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey("samples.id", ondelete="CASCADE"), index=True)
    total_mb = Column(Float)
    used_mb = Column(Float)

    sample = relationship("Sample", back_populates="disk")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Memory Metrics
class MemoryUsage(Base):
    __tablename__ = "memory_usage"

    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey("samples.id", ondelete="CASCADE"), unique=True, index=True)
    total_mb = Column(Float)
    used_mb = Column(Float)

    sample = relationship("Sample", back_populates="memory")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def create_database_engine(database_file_path):
    """Create and return a SQLAlchemy engine"""

    # Create SQLite engine
    engine = create_engine(f'sqlite:///{database_file_path}', echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    return engine

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_session(database_file_path):
    """Get a database session"""

    try:
        engine = create_database_engine(database_file_path)
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()
    except Exception as e:
        print(f"Error occurred while getting database session: {e}")
        return None