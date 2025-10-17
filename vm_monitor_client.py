#!/usr/bin/env python3
import psutil
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
import subprocess
from dataclasses import dataclass
from enum import Enum, auto

from vm_monitor_config import *

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SAMPLE_INTERVAL = 5      # seconds between samples
REPORT_INTERVAL = 60    # one hour (in seconds)

# nvidia-smi query parameters
TIME_STAMP='timestamp'
CHK_TEMP = 'temperature.gpu'
CHK_GPU = 'utilization.gpu'
CHK_MEM = 'utilization.memory'
CHK_MEM_TOTAL = 'memory.total'
CHK_MEM_FREE = 'memory.free'
CHK_MEM_USED = 'memory.used'

QUERIES = f'{CHK_GPU},{CHK_MEM_USED},{CHK_MEM_TOTAL}'

NVIDIA_SMI_COMMAND = f'nvidia-smi --query-gpu={QUERIES} --format=csv,noheader,nounits'

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dataclass
class UsageStats:

    cpu: list[float] = None
    mem_used_mb: int = 0
    mem_total_mb: int = 0

    disk_used_mb: int = 0
    disk_total_mb: int = 0

    gpu_proc: float = 0.0
    gpu_mem_used: int = 0
    gpu_mem_total: int = 0

    def __str__(self):
        return (f"CPU: {self.cpu}%, MEM: {self.mem_used_mb}/{self.mem_total_mb} MB, "
                f"DISK: {self.disk_used_mb}/{self.disk_total_mb} MB, "
                f"GPU: {self.gpu_proc}%, GPU_MEM: {self.gpu_mem_used}/{self.gpu_mem_total} MB")

    def __repr__(self) -> str:
        return self.__str__()

    def reset(self):

        self.cpu = [0.0] * len(self.cpu)
        self.mem_used_mb = 0
        self.mem_total_mb = 0
        self.disk_used_mb = 0
        self.disk_total_mb = 0
        self.gpu_proc = 0.0
        self.gpu_mem_used = 0
        self.gpu_mem_total = 0


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class GPUType(Enum):

    CPU_ONLY = auto()
    NVIDIA_GPU = auto()
    AMD_GPU = auto()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class VMMonitor():

    def __init__(self):
        self.gpu_type = self.check_gpu_type()

        self.logger = self.setup_logger()

        self.num_cpus = psutil.cpu_count(logical=True)
        self.peak_usage_stats = UsageStats(cpu=[0.0] * self.num_cpus)
        self.current_usage_stats = UsageStats(cpu=[0.0] * self.num_cpus)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def check_gpu_type(self):

        if subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True):
            return GPUType.NVIDIA_GPU
        elif subprocess.run(['rocm-smi'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True):
            return GPUType.AMD_GPU
        else:
            return GPUType.CPU_ONLY

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def setup_logger(self):

        logger = logging.getLogger('systemMonitorLogger')
        logger.setLevel(logging.INFO)

        handler = TimedRotatingFileHandler(LOG_FILE, when='M', interval=1, backupCount=12)

        formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        return logger

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_current_gpu_usage(self):

        gpu_proc_usage = 0.0
        gpu_mem_used = 0.0
        gpu_mem_total = 0.0

        if self.gpu_type == GPUType.NVIDIA_GPU:
            result = subprocess.run(NVIDIA_SMI_COMMAND, shell=True, capture_output=True, text=True, check=True)
            gpu_proc_usage = float(result.stdout.split(',')[0].strip())
            gpu_mem_used = float(result.stdout.split(',')[1].strip())
            gpu_mem_total = float(result.stdout.split(',')[2].strip())
        elif self.gpu_type == GPUType.AMD_GPU:
            pass

        self.current_usage_stats.gpu_proc = gpu_proc_usage
        self.current_usage_stats.gpu_mem_used = gpu_mem_used
        self.current_usage_stats.gpu_mem_total = gpu_mem_total

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_current_usage(self):
        cpu = psutil.cpu_percent(interval=1, percpu=True)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        self.current_usage_stats.cpu = cpu
        self.current_usage_stats.mem_used_mb = mem.used // (1024 * 1024)
        self.current_usage_stats.mem_total_mb = mem.total // (1024 * 1024)
        self.current_usage_stats.disk_used_mb = disk.used // (1024 * 1024)
        self.current_usage_stats.disk_total_mb = disk.total // (1024 * 1024)

        if not self.gpu_type == GPUType.CPU_ONLY:
            self.get_current_gpu_usage()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def update_peak_usage(self):

        for i in range(self.num_cpus):
            self.peak_usage_stats.cpu[i] = max(self.peak_usage_stats.cpu[i], self.current_usage_stats.cpu[i])

        self.peak_usage_stats.mem_used_mb = max(self.peak_usage_stats.mem_used_mb, self.current_usage_stats.mem_used_mb)
        self.peak_usage_stats.disk_used_mb = max(self.peak_usage_stats.disk_used_mb, self.current_usage_stats.disk_used_mb)

        self.peak_usage_stats.mem_total_mb = self.current_usage_stats.mem_total_mb
        self.peak_usage_stats.disk_total_mb = self.current_usage_stats.disk_total_mb

        if not self.gpu_type == GPUType.CPU_ONLY:
            self.peak_usage_stats.gpu_proc = max(self.peak_usage_stats.gpu_proc, self.current_usage_stats.gpu_proc)
            self.peak_usage_stats.gpu_mem_used = max(self.peak_usage_stats.gpu_mem_used, self.current_usage_stats.gpu_mem_used)
            self.peak_usage_stats.gpu_mem_total = self.current_usage_stats.gpu_mem_total

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_cpu_peak_str(self):
        if self.num_cpus == 1:
            return f"{self.peak_usage_stats.cpu[0]:.1f}"
        else:
            avg_cpu = sum(self.peak_usage_stats.cpu) / self.num_cpus
            return f"{avg_cpu:.1f} ({', '.join(f'{c:.1f}' for c in self.peak_usage_stats.cpu)})"

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def display(self):
        print(f"Current Usage: {self.current_usage_stats}")
        print(f"Peak Usage: {self.peak_usage_stats}")
        print("-" * len(str(self.current_usage_stats)))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def log_peak_stats(self):

        self.logger.info(self.peak_usage_stats)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def run(self):

        next_report = datetime.now() + timedelta(seconds=REPORT_INTERVAL)

        while True:
            self.get_current_usage()

            self.update_peak_usage()

            self.display()

            # check if it's time to log the hourly peak
            if datetime.now() >= next_report:

                self.log_peak_stats()
                # reset peak stats for the next interval
                self.peak_usage_stats.reset()

                # reset the next report time
                next_report = datetime.now() + timedelta(seconds=REPORT_INTERVAL)

            time.sleep(SAMPLE_INTERVAL)

# =================================================================================

def main():

    monitor = VMMonitor()
    monitor.run()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == "__main__":
    main()
