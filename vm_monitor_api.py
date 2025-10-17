import datetime

from flask import Flask, jsonify, request
from pprint import pprint

from vm_monitor_config import *

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

app = Flask(__name__)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_data_in_range(start_date, end_date):

    usage_data = []

    with open(LOG_FILE, 'r') as f:
        for line in f:
            try:
                timestamp_str, usage_data_str = line.split(' - ', 1)
                time_stamp = datetime.datetime.fromisoformat(timestamp_str)
            except ValueError:
                continue

            if start_date <= time_stamp <= end_date:
                    usage_data.append({timestamp_str :usage_data_str.strip()})

    return usage_data

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_start_date(start_date_str):
    start_date = datetime.datetime.fromisoformat(start_date_str)
    start_date = start_date.replace(hour=0, minute=0, second=0)

    return start_date

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_end_date(end_date_str):
    end_date = datetime.datetime.fromisoformat(end_date_str)
    end_date = end_date.replace(hour=23, minute=59, second=59)

    return end_date


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@app.route('/get_usage_data', methods=['GET'])
def get_usage_data():

    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')

    start_date = get_start_date(start_date_str)
    end_date = get_end_date(end_date_str)

    if not start_date or not end_date:
        return jsonify({'error': 'start and end dates are required'}), 400

    data = []

    try:
        data = get_data_in_range(start_date, end_date)
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use ISO format (YYYY-MM-DD'}), 400


    return jsonify(data)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

    # start_date = get_start_date("2025-10-29")
    # end_date = get_end_date("2025-10-29")

    # data = get_data_in_range(start_date, end_date)

    # pprint(data)