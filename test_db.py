import os
import datetime
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pprint import pprint


# Import your database models and Base from vm_monitor_db
from vm_monitor_db import Base, Sample, CPUUsage, GPUUsage, DiskUsage, MemoryUsage

# Create a temporary SQLite database for testing
TEST_DB_FILE = "test_db.db"
DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)
session = Session()

# Create all tables
Base.metadata.create_all(engine)

# Insert made-up test data

start_time = datetime.datetime.now() - datetime.timedelta(days=7)
datetimes = [start_time + datetime.timedelta(hours=i) for i in range(7 * 24)]

for dt in datetimes:
    sample = Sample(timestamp=dt, cpu_count=4, gpu_count=1)

    # CPU Usage
    for cpu_index in range(4):  # Assume 4 CPUs
        cpu_usage = CPUUsage(cpu_index=cpu_index,
                             usage_percent=random.uniform(0, 100))
        sample.cpus.append(cpu_usage)

    # GPU Usage
    for gpu_index in range(1):  # Assume 1 GPU
        gpu_usage = GPUUsage(
            gpu_index=gpu_index,
            usage_percent=random.uniform(0, 100),
            memory_used_mb=random.uniform(0, 8192),
            memory_total_mb=8192
        )
        sample.gpus.append(gpu_usage)

    # Disk Usage
    disk_usage = DiskUsage(
        total_mb=512000,
        used_mb=random.uniform(0, 512000)
    )
    sample.disk = disk_usage

    # Memory Usage
    memory_usage = MemoryUsage(
        total_mb=16384,
        used_mb=random.uniform(0, 16384)
    )
    sample.memory = memory_usage

    session.add(sample)

session.commit()
session.close()
print(f"Test database created at {TEST_DB_FILE}")
