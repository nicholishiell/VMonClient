#!/usr/bin/env python3
import psutil
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SAMPLE_INTERVAL = 10      # seconds between samples
REPORT_INTERVAL = 3600    # one hour (in seconds)

LOG_DIR = Path("/var/log/system_monitor")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "usage_peak.log"
LOG_FORMAT_CPU_ONLY = "%(asctime)s,%(cpu_peak).1f%%,%(mem_peak).1f%%/%(mem_total).1f%%,%(disk_peak).1f%%/%(disk_total).1f%%"
LOG_FORMAT_GPU = LOG_FORMAT_CPU_ONLY+",%(gpu_proc_peak).1f%%,%(gpu_mem_peak).1f%%/%(gpu_mem_total).1f%%"

TIME_STAMP='timestamp'
CHK_TEMP = 'temperature.gpu'
CHK_GPU = 'utilization.gpu'
CHK_MEM = 'utilization.memory'
CHK_MEM_TOTAL = 'memory.total'
CHK_MEM_FREE = 'memory.free'
CHK_MEM_USED = 'memory.used'

QUERIES = f'{CHK_GPU},{CHK_MEM_USED},{CHK_MEM_TOTAL}'

NVIDIA_SMI_COMMAND = f'nvidia-smi --query-gpu={QUERIES} --format=csv,noheader,nounits'

NVIDIA_GPU = 'NVIDIA_GPU'
AMD_GPU = 'AMD_GPU'

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def setup_logger(gpu_type=None):

    logger = logging.getLogger('systemMonitorLogger')
    logger.setLevel(logging.INFO)

    handler = TimedRotatingFileHandler(LOG_FILE, when='M', interval=1, backupCount=12)

    if cpu_only:
        handler.setFormatter(logging.Formatter(LOG_FORMAT_CPU_ONLY))
    else:
        handler.setFormatter(logging.Formatter(LOG_FORMAT_GPU))

    logger.addHandler(handler)

    return logger

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def has_nvidia_gpu():
    try:
        subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def has_amd_gpu():
    pass

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_gpu_stats(gpu_type):

    gpu_proc_usage = gpu_mem_used = gpu_mem_total = 0

    if gpu_type == NVIDIA_GPU:
        result = subprocess.run(NVIDIA_SMI_COMMAND, shell=True, capture_output=True, text=True, check=True)
        gpu_proc_usage = float(result.stdout.split(',')[0].strip())
        gpu_mem_used = float(result.stdout.split(',')[1].strip())
        gpu_mem_total = float(result.stdout.split(',')[2].strip())
    elif gpu_type == AMD_GPU:
        pass

    return {"gpu_proc_usage": gpu_proc_usage,
            "gpu_mem_used": gpu_mem_used,
            "gpu_mem_total": gpu_mem_total}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_usage(gpu_type=None):
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    usage = {   "cpu": cpu,
                "mem_used_mb": mem.used / (1024 * 1024),
                "mem_total_mb": mem.total / (1024 * 1024),
                "disk_used_mb": disk.used / (1024 * 1024),
                "disk_total_mb": disk.total / (1024 * 1024),}

    if gpu_type:
        gpu = get_gpu_stats(gpu_type)
        usage.update({  "gpu_proc": gpu["gpu_proc_usage"],
                        "gpu_mem_used": gpu["gpu_mem_used"],
                        "gpu_mem_total": gpu["gpu_mem_total"]})

    return usage

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_gpu_type():

    if has_nvidia_gpu():
        return NVIDIA_GPU
    elif has_amd_gpu():
        return AMD_GPU
    else:
        return None

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():

    # determine if there is GPU and if so whether it is NVidia or AMD
    gpu_type = check_gpu_type()

    # initialize logger
    logger = setup_logger(gpu_type)

    # initialize next report time
    next_report = datetime.now() + timedelta(seconds=REPORT_INTERVAL)

    # initialize peaks
    cpu_peak = mem_peak = disk_peak = gpu_peak = gpu_mem_peak = 0

    while True:
        usage = get_usage(gpu_type)

        # get common usage stats
        cpu_peak = max(cpu_peak, usage["cpu"])
        mem_peak = max(mem_peak, usage["mem_used_mb"] )
        disk_peak = max(disk_peak, usage["disk_used_mb"] )

        # get GPU usage stats if applicable
        if gpu_type:
            gpu_peak = max(gpu_peak, usage["gpu_proc"])
            gpu_mem_peak = max(gpu_mem_peak, usage["gpu_mem_used"])

        # check if it's time to log the hourly peak
        if datetime.now() >= next_report:
            logger.info("", extra={"cpu_peak": cpu_peak,
                                    "mem_peak": mem_peak,
                                    "disk_peak": disk_peak,
                                    "gpu_peak": gpu_peak,
                                    "gpu_mem_peak": gpu_mem_peak})

            # reset for next hour
            cpu_peak = mem_peak = disk_peak = gpu_peak = gpu_mem_peak = 0

            next_report = datetime.now() + timedelta(seconds=REPORT_INTERVAL)

        time.sleep(SAMPLE_INTERVAL)

if __name__ == "__main__":
    main()