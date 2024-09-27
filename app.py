from flask import Flask, request, jsonify, render_template
from datetime import datetime
import os
import re


app = Flask(__name__)

# Route to render the main page
@app.route('/')
def index():
    archive_log()  # Archive old log entries before rendering the main page
    return render_template('index.html')

# Function to archive old log entries to archive.txt
def archive_log():
    log_file = 'log.txt'
    archive_file = 'archive.txt'

    with open(log_file, 'r') as f:
        log_entries = f.readlines()  # Read all log entries from log.txt

    # If there are more than 100 entries, we need to archive the older ones
    if len(log_entries) > 100:
        recent_entries = log_entries[-100:]  # Keep the most recent 100 entries
        older_entries = log_entries[:-100]   # Get all older entries

        # Overwrite log.txt with the most recent 100 entries
        with open(log_file, 'w') as f:
            f.writelines(recent_entries)

        # Append older entries to archive.txt
        with open(archive_file, 'a') as f:
            f.writelines(older_entries)

        print(f"Archived {len(older_entries)} rows to {archive_file}.")
    else:
        print(f"No need to archive. {len(log_entries)} rows in log.txt.")

# Route to fetch the log contents and return them in reverse order
@app.route('/get_log', methods=['GET'])
def get_log():
    try:
        with open('log.txt', 'r') as f:
            log_entries = f.readlines()
        log_entries.reverse()  # Reverse the order to show the latest entries first
        return jsonify(log_entries=log_entries)
    except FileNotFoundError:
        return jsonify(log_entries=[])
        
# Route to update log.txt with new content
@app.route('/update_log', methods=['POST'])
def update_log():
    try:
        # Get the new log content from the request
        new_log_content = request.json['log']
        # Split the log content by lines and reverse the order
        log_lines = new_log_content.splitlines()  # Split the content into lines
        reversed_log_content = "\n".join(reversed(log_lines)) + "\n"  # Reverse the lines and join them back with newlines
        
        # Overwrite log.txt with the new content
        with open('log.txt', 'w') as f:
            f.write(reversed_log_content)

        # Return success response
        return jsonify(success=True)
    except Exception as e:
        # Return error response in case of failure
        return jsonify(success=False, error=str(e))

# Route to handle adding a new activity
@app.route('/add_activity', methods=['POST'])
def add_activity():
    data = request.json
    print(f"Received data: {data}")  # Debugging line
    time = data['time']
    activity = data['activity']
    notes = data['notes'] if data['notes'] else 'no notes'

    # Append the new activity to log.txt
    with open('log.txt', 'a') as f:
        f.write(f"{time},{activity},{notes}\n")

    # Return success and the updated log
    with open('log.txt', 'r') as f:
        log_entries = f.readlines()
    log_entries.reverse()  # Return the log in reverse order
    return jsonify(success=True, log_entries=log_entries)


# Route to sort the log entries by timestamp and overwrite log.txt
@app.route('/sort_log', methods=['POST'])
def sort_log():
    try:
        # Read log entries from log.txt
        with open('log.txt', 'r') as f:
            log_entries = f.readlines()

        # Sort the log entries by timestamp (first element in each line)
        log_entries_sorted = sorted(log_entries, key=lambda x: datetime.strptime(x.split(',')[0], '%Y-%m-%dT%H:%M'))

        # Overwrite log.txt with the sorted entries
        with open('log.txt', 'w') as f:
            f.writelines(log_entries_sorted)

        return jsonify(success=True, message="Log sorted successfully")
    except Exception as e:
        return jsonify(success=False, error=str(e))

# Helper function to load log and archive data
def load_log_data(withArchive = False):
    data = []
    log_file = 'log.txt'
    
    # Load archive.txt data, load it first to keep time stamps in order
    if (withArchive):
        archive_file = 'archive.txt'
        with open(archive_file, 'r') as f:
            data += f.readlines()

    # Load log.txt data
    with open(log_file, 'r') as f:
        data += f.readlines()

    return data

# Helper function to count diapers (wet and dirty)
def diaper_stats(data):
    wet_count = 0
    dirty_count = 0
    today = datetime.now().strftime('%Y-%m-%d')
    
    for entry in data:
        if "diaper" in entry and today in entry:
            if "wet" in entry or "mixed" in entry:
                wet_count += 1
            if "poo" in entry or "mixed" in entry:
                dirty_count += 1
                
    return wet_count, dirty_count

# Helper function to find time since last nap
def time_since_last_nap(data):
    now = datetime.now()
    
    if data and "asleep" in data[-1]:
        return 0

    for entry in reversed(data):
        if "awake" in entry:
            timestamp_str, activity, notes = entry.split(",", 2)
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
            time_elapsed = (now - timestamp).total_seconds() // 60
            return int(time_elapsed)

    return None

# Helper function to count naps today
def nap_count(data):
    today = datetime.now().strftime('%Y-%m-%d')
    nap_count = 0
    
    for entry in data:
        if "asleep" in entry and today in entry:
            nap_count += 1
    
    return nap_count

# Helper function to calculate total nap time today
def total_nap_time(data):
    today = datetime.now().strftime('%Y-%m-%d')
    total_nap_time = 0
    last_awake_time = None

    for entry in data:
        if "awake" in entry:
            timestamp_str, activity, notes = entry.split(",", 2)
            if today in timestamp_str:
                last_awake_time = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
        elif "asleep" in entry and last_awake_time:
            timestamp_str, activity, notes = entry.split(",", 2)
            if today in timestamp_str:
                asleep_time = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
                nap_duration = (asleep_time - last_awake_time).total_seconds() // 60
                total_nap_time += int(nap_duration)
                last_awake_time = None

    if last_awake_time:  # If the last entry is "asleep"
        total_nap_time += (datetime.now() - last_awake_time).total_seconds() // 60
    
    return total_nap_time

# Helper function to count feedings today
def feeding_count(data):
    today = datetime.now().strftime('%Y-%m-%d')
    count = 0
    
    for entry in data:
        if "feeding" in entry and today in entry:
            count += 1
    
    return count

# Helper function to calculate total feeding amount today
def feeding_amount(data):
    today = datetime.now().strftime('%Y-%m-%d')
    total_amount = 0
    ml_pattern = re.compile(r'(\d+)\s*mL', re.IGNORECASE)

    for entry in data:
        if today in entry:
            match = ml_pattern.search(entry.split(",")[2])  # Searching in the notes section
            if match:
                total_amount += int(match.group(1))

    return total_amount

# Master function to load daily stats
@app.route('/load_daily_stats', methods=['GET'])
def load_daily_stats():
    data = load_log_data()  # Load log data once

    wet_count, dirty_count = diaper_stats(data)
    time_since_nap = time_since_last_nap(data)
    nap_count_today = nap_count(data)
    total_nap_time_today = total_nap_time(data)
    feeding_count_today = feeding_count(data)
    total_feeding_amount = feeding_amount(data)
    print([wet_count, dirty_count, time_since_nap, nap_count_today, total_nap_time_today, feeding_count_today, total_feeding_amount])
    # Return all stats in one JSON response
    return jsonify({
        'wet_count': wet_count,
        'dirty_count': dirty_count,
        'time_since_nap': time_since_nap,
        'nap_count': nap_count_today,
        'total_nap_time': total_nap_time_today,
        'feeding_count': feeding_count_today,
        'total_feeding_amount': total_feeding_amount
    })

if __name__ == '__main__':
    app.run()
