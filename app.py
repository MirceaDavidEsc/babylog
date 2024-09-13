from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')  # Renders index.html from the 'templates' folder
    

# Route to fetch the log contents and return them in reverse order
@app.route('/get_log', methods=['GET'])
def get_log():
    try:
        with open('log.txt', 'r') as f:
            log_entries = f.readlines()
            
        # Parse each line, extract the timestamp, and sort by timestamp
        log_entries_sorted = sorted(log_entries, key=lambda x: datetime.strptime(x.split(',')[0], '%Y-%m-%dT%H:%M:%S'), reverse=True)

        return jsonify(log_entries=log_entries_sorted)
    except FileNotFoundError:
        return jsonify(log_entries=[])


# Route to handle adding a new activity
@app.route('/add_activity', methods=['POST'])
def add_activity():
    data = request.json
    time = data['time']
    activity = data['activity']
    notes = data['notes'] if data['notes'] else 'no notes'

    # Append the new activity to log.txt
    with open('log.txt', 'a') as f:
        f.write(f"{time},{activity},{notes}\n")

    # Sort log entries by time in descending order (most recent first)
    log_entries_sorted = sorted(log_entries, key=lambda x: datetime.strptime(x.split(',')[0], '%Y-%m-%dT%H:%M:%S'), reverse=True)
    return jsonify(success=True, log_entries=log_entries_sorted)

if __name__ == '__main__':
    app.run()
