from flask import Flask, request, jsonify, render_template

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
        log_entries.reverse()  # Reverse the order to show the latest entries first
        return jsonify(log_entries=log_entries)
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

    # Return success and the updated log
    get_log()

# Trigger refresh
if __name__ == '__main__':
    app.run()
