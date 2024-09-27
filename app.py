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

# Helper function to filter diaper entries for today
def filter_diapers_for_today(data):
    today = datetime.now().strftime('%Y-%m-%d')  # Get today's date in YYYY-MM-DD format
    wet_count = 0
    dirty_count = 0

    for entry in data:
        # Only process entries with "diaper"
        if "diaper" in entry:
            timestamp, activity, notes = entry.split(",", 2)  # Split the entry into components
            
            # Check if the timestamp is from today
            if today in timestamp:
                # Tally up wet and dirty diapers
                if "wet" in activity or "mixed" in activity:
                    wet_count += 1
                if "poo" in activity or "mixed" in activity:
                    dirty_count += 1

    return wet_count, dirty_count



# New route to fetch daily diaper totals
@app.route('/get_daily_diaper_totals', methods=['GET'])
def get_daily_diaper_totals():
    # Load log data and archive data
    log_data = load_log_data(False)

    # Filter and count diapers for today
    wet_count, dirty_count = filter_diapers_for_today(log_data)
    print("Wet: " + str(wet_count) + " Dirty: " + str(dirty_count))
    # Return the counts as JSON
    return jsonify({
        'wet': wet_count,
        'dirty': dirty_count
    })


# Helper function to find the most recent "awake" entry
def time_since_last_nap(data):
    now = datetime.now()
    
    # If the latest entry was "asleep", baby is still asleep, so return 0
    if data and "asleep" in data[-1]: 
        return 0
    
    # Iterate over the log data in reverse order to find the most recent "awake" entry
    for entry in reversed(data):
        print(entry)
        if "awake" in entry:
            timestamp_str, activity, notes = entry.split(",", 2)  # Split the entry into components
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
            time_elapsed = (now - timestamp).total_seconds() // 60  # Convert to minutes
            return int(time_elapsed)

    # If no "awake" entry is found, return None
    return None


# New route to fetch the time since the last nap
@app.route('/get_time_since_last_nap', methods=['GET'])
def get_time_since_last_nap():
    # Load log data and archive data
    log_data = load_log_data(False)

    # Find the time since the last "awake" entry
    minutes_since_last_nap = time_since_last_nap(log_data)

    # Return the result as JSON
    if minutes_since_last_nap is not None:
        return jsonify({
            'time_since_nap': minutes_since_last_nap
        })
    else:
        return jsonify({
            'time_since_nap': "No nap found"
        })

# Helper function to count naps for today
def count_naps_today():
    data = load_log_data(withArchive=False)  # Load only log.txt data
    today = datetime.now().strftime('%Y-%m-%d')  # Get today's date in YYYY-MM-DD format
    nap_count = 0

    # Iterate through the log and count "asleep" entries for today
    for entry in data:
        if "asleep" in entry:
            timestamp_str, activity, notes = entry.split(",", 2)
            if today in timestamp_str:
                nap_count += 1

    return nap_count

# New route to fetch the number of naps for today
@app.route('/get_nap_count', methods=['GET'])
def get_nap_count():
    nap_count = count_naps_today()

    # Return the nap count as JSON
    return jsonify({
        'nap_count': nap_count
    })


# Helper function to calculate total nap time for today
def calculate_total_nap_time():
    data = load_log_data(withArchive=False)  # Only load log.txt data
    today = datetime.now().strftime('%Y-%m-%d')  # Get today's date in YYYY-MM-DD format
    total_nap_time = 0
    last_awake_time = None  # Track the last "awake" time
    last_asleep_time = None  # Track the last "asleep" time in case the last entry is asleep

    # Iterate over the log entries
    for entry in data:
        if "awake" in entry:
            timestamp_str, activity, notes = entry.split(",", 2)
            if today in timestamp_str:
                last_awake_time = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
                last_asleep_time = None  # Reset asleep time when awake is encountered

        elif "asleep" in entry and last_awake_time:
            timestamp_str, activity, notes = entry.split(",", 2)
            if today in timestamp_str:
                asleep_time = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
                # Calculate the nap time and add to total
                nap_duration = (asleep_time - last_awake_time).total_seconds() // 60  # In minutes
                total_nap_time += int(nap_duration)
                last_awake_time = None  # Reset awake time after counting the nap
                last_asleep_time = asleep_time  # Track the last asleep time

    # Special condition: if the last entry is "asleep", add nap time from "asleep" to now
    if last_asleep_time:
        now = datetime.now()
        nap_duration = (now - last_asleep_time).total_seconds() // 60  # In minutes
        total_nap_time += int(nap_duration)

    return total_nap_time


# New route to fetch total nap time for today
@app.route('/get_total_nap_time', methods=['GET'])
def get_total_nap_time():
    total_nap_time = calculate_total_nap_time()

    # Return the total nap time as JSON
    return jsonify({
        'total_nap_time': total_nap_time
    })


# Helper function to count feedings for today
def feedingCountToday():
    data = load_log_data(withArchive=False)  # Load only log.txt data
    today = datetime.now().strftime('%Y-%m-%d')  # Get today's date in YYYY-MM-DD format
    feeding_count = 0

    # Iterate through the log and count "feeding" entries for today
    for entry in data:
        if "feeding" in entry:
            timestamp_str, activity, notes = entry.split(",", 2)
            if today in timestamp_str:
                feeding_count += 1

    return feeding_count

# New route to get the number of feedings for today
@app.route('/get_feeding_count', methods=['GET'])
def get_feeding_count():
    feeding_count = feedingCountToday()

    # Return the feeding count as JSON
    return jsonify({
        'feeding_count': feeding_count
    })

# Helper function to calculate total feeding amount for today
def feedingAmountToday():
    data = load_log_data(withArchive=False)  # Load only log.txt data
    today = datetime.now().strftime('%Y-%m-%d')  # Get today's date in YYYY-MM-DD format
    total_amount = 0

    # Regular expression to match "mL" in a case-insensitive way
    ml_pattern = re.compile(r'(\d+)\s*mL', re.IGNORECASE)

    # Iterate through the log and find feeding amounts for today
    for entry in data:
        timestamp_str, activity, notes = entry.split(",", 2)
        if today in timestamp_str:
            # Search for "mL" in the comments/notes and extract the amount
            match = ml_pattern.search(notes)
            if match:
                total_amount += int(match.group(1))  # Sum the numeric values

    return total_amount

# New route to get the total feeding amount for today
@app.route('/get_feeding_amount', methods=['GET'])
def get_feeding_amount():
    feeding_amount = feedingAmountToday()

    # Return the total feeding amount as JSON
    return jsonify({
        'feeding_amount': feeding_amount
    })


if __name__ == '__main__':
    app.run()
