#!/usr/bin/env python3
import psutil
import time
import logging
import argparse
import yaml

from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pprint import pprint

from vm_monitor_db import get_session, Sample, CPUUsage, MemoryUsage, DiskUsage, GPUUsage
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SAMPLE_INTERVAL = 'sample_interval'      # seconds between samples
REPORT_INTERVAL = 'report_interval'    # one hour (in seconds)
DB_FILE_PATH = 'db_file_path'                # directory to store log files

REQUIRED_KEYS = [SAMPLE_INTERVAL, REPORT_INTERVAL, DB_FILE_PATH]

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

    def __init__(   self,
                    sample_interval : int = 5,
                    report_interval : int = 60,
                    db_file_path : str ='vm_monitor.db'):

        self.sample_interval = sample_interval
        self.report_interval = report_interval
        self.db_session = get_session(db_file_path)

        self.gpu_type = self.check_gpu_type()

        self.num_gpus = 0 if self.gpu_type == GPUType.CPU_ONLY else 1
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

    def get_current_gpu_usage(self):

        gpu_proc_usage = 0.0
        gpu_mem_used = 0.0
        gpu_mem_total = 0.0

        if self.gpu_type == GPUType.NVIDIA_GPU:
            result = subprocess.run(NVIDIA_SMI_COMMAND, shell=True, capture_output=True, text=True, check=True)
            gpu_proc_usage = float(result.stdout.split(',')[0].strip())
            gpu_mem_used = int(result.stdout.split(',')[1].strip())
            gpu_mem_total = int(result.stdout.split(',')[2].strip())
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
    # TODO: I dont think this is used anywhere
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

        sample = Sample(timestamp=datetime.now(),
                        cpu_count=self.num_cpus,
                        gpu_count=self.num_gpus)
        self.db_session.add(sample)
        self.db_session.commit()

        for i, cpu_usage in enumerate(self.peak_usage_stats.cpu):
            cpu_record = CPUUsage(  sample_id=sample.id,
                                    cpu_index=i,
                                    usage_percent=cpu_usage)
            self.db_session.add(cpu_record)

        mem_record = MemoryUsage(   sample_id=sample.id,
                                    total_mb=self.peak_usage_stats.mem_total_mb,
                                    used_mb=self.peak_usage_stats.mem_used_mb)

        self.db_session.add(mem_record)

        disk_record = DiskUsage(sample_id=sample.id,
                                total_mb=self.peak_usage_stats.disk_total_mb,
                                used_mb=self.peak_usage_stats.disk_used_mb)
        self.db_session.add(disk_record)

        if not self.gpu_type == GPUType.CPU_ONLY:
            gpu_record = GPUUsage(  sample_id=sample.id,
                                    gpu_index=0,
                                    usage_percent=self.peak_usage_stats.gpu_proc,
                                    memory_used_mb=self.peak_usage_stats.gpu_mem_used,
                                    memory_total_mb=self.peak_usage_stats.gpu_mem_total)
            self.db_session.add(gpu_record)

        self.db_session.commit()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def run(self):

        next_report = datetime.now() + timedelta(seconds=self.report_interval)

        while True:
            self.get_current_usage()

            self.update_peak_usage()

            # check if it's time to log the hourly peak
            if datetime.now() >= next_report:

                self.log_peak_stats()

                # reset peak stats for the next interval
                self.peak_usage_stats.reset()

                # reset the next report time
                next_report = datetime.now() + timedelta(seconds=self.report_interval)

            time.sleep(self.sample_interval)

# =================================================================================

def main(config_dict : dict):

    monitor = VMMonitor(sample_interval=config_dict[SAMPLE_INTERVAL],
                        report_interval=config_dict[REPORT_INTERVAL],
                        db_file_path=config_dict[DB_FILE_PATH])
    monitor.run()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def validate_config(config_dict : dict) -> bool:

    for key in REQUIRED_KEYS:
        if key not in config_dict:
            print(f"Missing required config key: {key}")
            return False

    return True

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == "__main__":

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="VM Monitor Client")
    parser.add_argument('--config', type=str, required=True, help='Path to config YAML file')
    args = parser.parse_args()

    # Load configuration from YAML file
    config = {}
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if validate_config(config):
        main(config)
    else:
        print("Invalid configuration. Please check the config file.")
