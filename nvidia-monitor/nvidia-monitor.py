import subprocess
import time
import logging
from logging.handlers import TimedRotatingFileHandler

SAMPLE_TIME = 900  # In seconds

LOG_FILE = 'gpu_stats.log'

TIME_STAMP='timestamp'
CHK_TEMP = 'temperature.gpu'
CHK_GPU = 'utilization.gpu'
CHK_MEM = 'utilization.memory'
CHK_MEM_TOTAL = 'memory.total'
CHK_MEM_FREE = 'memory.free'
CHK_MEM_USED = 'memory.used'

QUERIES = f'{TIME_STAMP},{CHK_TEMP},{CHK_GPU},{CHK_MEM},{CHK_MEM_TOTAL},{CHK_MEM_FREE},{CHK_MEM_USED}'

NVIDIA_SMI_COMMAND = f'nvidia-smi --query-gpu={QUERIES} --format=csv'


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def extract_gpu_stats(result):
    lines = result.stdout.split('\n')
    
    values = None
    if  len(lines) == 3:
        values = lines[1]
    
    return values

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def setup_logger():
    logger = logging.getLogger('GPUStatsLogger')
    logger.setLevel(logging.INFO)
    
    handler = TimedRotatingFileHandler(LOG_FILE, when='W0', interval=1, backupCount=12)
    handler.setFormatter(logging.Formatter('%(message)s'))
    
    logger.addHandler(handler)
    
    return logger

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():
    
    while True:
        stats = extract_gpu_stats(subprocess.run(NVIDIA_SMI_COMMAND, shell=True, capture_output=True, text=True))
              
        if stats is not None:
            logger.log(msg=stats, level=logging.INFO)

        time.sleep(SAMPLE_TIME)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == '__main__':
    logger = setup_logger()

    main()