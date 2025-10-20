#!/usr/bin/env python3

import datetime
import argparse
import yaml
from flask import Flask, jsonify, request
from contextlib import contextmanager

from vm_monitor_db import get_session, Sample, CPUUsage, MemoryUsage, DiskUsage, GPUUsage

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HOST_IP = 'host_ip'                # Host IP address
PORT_NUMBER = 'port_number'            # Port number for the API
DB_FILE_PATH = 'db_file_path'                # directory to store log files

REQUIRED_KEYS = [HOST_IP, PORT_NUMBER, DB_FILE_PATH]

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class VMMonitorAPI:
    """Flask API for VM Monitor with database access"""

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(   self,
                    db_file_path):

        self.app = Flask(__name__)
        self._register_routes()

        self.database_path = db_file_path

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @contextmanager
    def get_db_session(self):
        """Context manager for database sessions"""
        session = get_session(self.database_path)
        try:
            yield session
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _register_routes(self):
        """Register Flask routes"""
        self.app.route('/get_usage_data', methods=['GET'])(self.get_usage_data)
        self.app.route('/check_up', methods=['GET'])(self.get_check_up)
        self.app.route('/purge', methods=['POST'])(self.post_purge)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_data_in_range(self, start_date, end_date):
        """Get usage data from database within date range"""
        with self.get_db_session() as session:
            # Query samples in date range
            samples = session.query(Sample).filter( Sample.timestamp >= start_date,
                                                    Sample.timestamp <= end_date).all()

            usage_data = []
            for sample in samples:
                sample_data = { 'timestamp': sample.timestamp.isoformat(),
                                'cpu_count': sample.cpu_count,
                                'gpu_count': sample.gpu_count,
                    'cpus': [ { 'cpu_index': cpu.cpu_index,
                                'usage_percent': cpu.usage_percent,} for cpu in sample.cpus],
                    'gpus': [{  'gpu_index': gpu.gpu_index,
                                'usage_percent': gpu.usage_percent,
                                'memory_used_mb': gpu.memory_used_mb,
                                'memory_total_mb': gpu.memory_total_mb} for gpu in sample.gpus],
                    'disk': {   'total_mb': sample.disk.total_mb,
                                'used_mb': sample.disk.used_mb} if sample.disk else None,
                    'memory': { 'total_mb': sample.memory.total_mb,
                                'used_mb': sample.memory.used_mb} if sample.memory else None
                }
                usage_data.append(sample_data)

            return usage_data

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_start_date(self, start_date_str):
        """Convert date string to datetime at start of day"""
        start_date = datetime.datetime.fromisoformat(start_date_str)
        return start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_end_date(self, end_date_str):
        """Convert date string to datetime at end of day"""
        end_date = datetime.datetime.fromisoformat(end_date_str)
        return end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_usage_data(self):
        """Flask route handler for getting usage data"""
        start_date_str = request.args.get('start')
        end_date_str = request.args.get('end')

        if not start_date_str or not end_date_str:
            return jsonify({'error': 'start and end dates are required'}), 400

        try:
            start_date = self.get_start_date(start_date_str)
            end_date = self.get_end_date(end_date_str)
            print(f"Fetching data from {start_date} to {end_date}")
            data = self.get_data_in_range(start_date, end_date)
            return jsonify({
                'status': 'success',
                'data': data,
                'count': len(data)
            })

        except ValueError as e:
            return jsonify({'error': f'Invalid date format. Use ISO format (YYYY-MM-DD): {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_check_up(self):
        """Flask route handler for health check"""
        return jsonify({'status': 'VM Monitor API is running'}), 200

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def post_purge(self):
        """Flask route handler for purging old data"""
        days_str = request.args.get('days')
        if not days_str:
            return jsonify({'error': 'days parameter is required'}), 400

        try:
            days = int(days_str)
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)

            with self.get_db_session() as session:
                deleted_count = session.query(Sample).filter(Sample.timestamp < cutoff_date).delete(synchronize_session=False)
                session.commit()

            return jsonify({
                'status': 'success',
                'deleted_count': deleted_count
            })

        except ValueError:
            return jsonify({'error': 'Invalid days parameter. Must be an integer.'}), 400
        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def run(self, host='0.0.0.0', port=8000, debug=False):
        """Run the Flask application"""
        self.app.run(host=host, port=port, debug=debug)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def validate_config(config):

    for key in REQUIRED_KEYS:
        if key not in config:
            print(f"Missing required config key: {key}")
            return False

    return True

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="VM Monitor Client")
    parser.add_argument('--config', type=str, required=True, help='Path to config YAML file')
    args = parser.parse_args()

    # Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # If all good run the API server
    if validate_config(config):
        api = VMMonitorAPI(db_file_path=config[DB_FILE_PATH])
        api.run(host=config[HOST_IP],
                port=config[PORT_NUMBER])
    else:
        print("Invalid configuration. Exiting.")