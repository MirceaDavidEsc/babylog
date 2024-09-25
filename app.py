from flask import Flask, request, jsonify, render_template
from datetime import datetime

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
        
#test
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
# Sorting log testing comment

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

if __name__ == '__main__':
    app.run()
