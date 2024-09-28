from flask import Flask, request, jsonify, render_template
from datetime import datetime
import re
import pandas as pd


app = Flask(__name__)

# Route to render the main page
@app.route('/')
def index():
    archive_log()  # Archive old log entries before rendering the main page
    return render_template('index.html')

# Function to archive old log entries to archive.txt
def archive_log(keep_length = 100):
    log_file = 'log.txt'
    archive_file = 'archive.txt'

    with open(log_file, 'r') as f:
        log_entries = f.readlines()  # Read all log entries from log.txt

    # If there are more than 100 entries, we need to archive the older ones
    if len(log_entries) > keep_length:
        recent_entries = log_entries[-keep_length:]  # Keep the most recent 100 entries
        older_entries = log_entries[:-keep_length]   # Get all older entries

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

def feeding_amount_df(notes):
    match = re.search(r'(\d+)\s*mL', notes, re.IGNORECASE)
    return int(match.group(1)) if match else 0

# Master function to load daily stats
@app.route('/load_daily_stats', methods=['GET'])
def load_daily_stats():
    data = load_log_data(False)  # Load log data once
    data_df = convert_log_to_df(data)
    
    # Calculate summary counts for all count data
    today_df = data_df[data_df['date'] == datetime.today().date()]
    today_df_summary = today_df.loc[:,'dirty_diaper':'feeding_amt'].sum().to_frame(name='sum')
    
    # Calculate sleep statistics
    today_sleep_durations, still_sleeping = calculate_sleep_durations(today_df)
    today_sleep_summary = today_sleep_durations.loc[:,'sleep_duration'].sum()
    
    if still_sleeping:
        time_since_nap = 0
    else:
        time_diff = datetime.now().replace(second=0,microsecond=0) - today_sleep_durations.iloc[-1]['awake'] 
        time_since_nap = time_diff.total_seconds() / 60
    
    # Return all stats in one JSON response
    return jsonify({
        'wet_count': str(today_df_summary.loc['wet_diaper','sum']),
        'dirty_count': str(today_df_summary.loc['dirty_diaper','sum']),
        'time_since_nap': str(time_since_nap),
        'nap_count': str(today_df_summary.loc['nap_flag','sum']),
        'total_nap_time': str(today_sleep_summary),
        'feeding_count': str(today_df_summary.loc['feed_flag','sum']),
        'total_feeding_amount': str(today_df_summary.loc['feeding_amt','sum'])
    })

# Helper function to turn the log into a pandas dataframe
def convert_log_to_df(log_data):
    
    rows = []
    for entry in log_data:
        timestamp_str, activity, notes = entry.split(",", 2)
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
        rows.append([timestamp, activity.strip(), notes])
            
    log_df = pd.DataFrame(rows, columns=["timestamp", "activity", "notes"])
    log_df['date'] = log_df['timestamp'].dt.date
    log_df['dirty_diaper'] = log_df['activity'].apply(lambda x: 1 if x in ['poo diaper', 'mixed diaper'] else 0)
    log_df['wet_diaper'] = log_df['activity'].apply(lambda x: 1 if x in ['wet diaper', 'mixed diaper'] else 0)
    log_df['nap_flag'] = log_df['activity'].apply(lambda x: 1 if x == 'asleep' else 0)
    log_df['feed_flag'] = log_df['activity'].apply(lambda x: 1 if x == 'feeding' else 0)
    log_df['feeding_amt'] = log_df['notes'].apply(feeding_amount_df)

    
    return(log_df)


def calculate_sleep_durations(log_df):
    # Filter rows for "asleep" and "awake" activities
    sleep_df = log_df[log_df['activity'].isin(['asleep', 'awake'])].copy()
    sleep_df.sort_values(by='timestamp', inplace=True)
    asleep_df = sleep_df[sleep_df['activity'] == 'asleep'].reset_index(drop=True)
    awake_df = sleep_df[sleep_df['activity'] == 'awake'].reset_index(drop=True)
    
    # Create a new DataFrame with both asleep and awake times
    sleep_periods = pd.DataFrame({
        'asleep': asleep_df['timestamp'],
        'awake': awake_df['timestamp']
    })
    
    # there is an off-by-one error, need to shift aslep windows down
    if sleep_periods.loc[0,'asleep'] > sleep_periods.loc[0,'awake']:
        if not pd.isna(sleep_periods.iloc[-1]['asleep']): # insert new row if needed
           sleep_periods = pd.concat([sleep_periods, pd.DataFrame({'asleep': [pd.NaT], 'awake': [pd.NaT]})], ignore_index=True)
        sleep_periods['asleep'] = sleep_periods['asleep'].shift(1)
     
    if (pd.isna(sleep_periods.iloc[-1]['awake'])):
        sleep_periods.at[sleep_periods.index[-1],'awake'] = datetime.now().replace(second=0,microsecond=0)
        still_running = True
    else:
        still_running = False
    
    sleep_periods['sleep_duration'] = (sleep_periods['awake'] - sleep_periods['asleep']).dt.total_seconds() / 60

    return [sleep_periods, still_running]


def flag_anomaly_sleep(log_df, drop=False):
    df = log_df.copy()
    df['anomaly_sleep'] = False
    df['next_activity'] = df['activity'].shift(-1)
    df['prev_activity'] = df['activity'].shift(1)
    condition_1 = (df['activity'] == 'asleep') & (df['next_activity'] != 'awake')
    condition_2 = (df['activity'] == 'awake') & (df['prev_activity'] != 'asleep')

    # Set anomaly_sleep to True where either condition is met
    df.loc[condition_1 | condition_2, 'anomaly_sleep'] = True
    # Drop the helper columns (next_activity and prev_activity)
    df.drop(columns=['next_activity', 'prev_activity'], inplace=True)

    # If drop=True, remove all rows where anomaly_sleep is True
    if drop:
        df = df[df['anomaly_sleep'] == False].copy()

    return df


if __name__ == '__main__':
    app.run()
