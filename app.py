from flask import Flask, request, jsonify, render_template, send_file
from datetime import datetime, timedelta, time
import re
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


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
        log_entries = load_log_data(False)
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
    archive_file = 'archive.txt'
    
    # Step 1: Check if log.txt exists, if not, create an empty log.txt
    if not os.path.exists(log_file):
        print(f"{log_file} does not exist. Creating an empty {log_file}.")
        open(log_file, 'w').close()  # Create an empty file
    
    # Step 2: Check if archive.txt exists (only if withArchive=True), if not, create an empty archive.txt
    if withArchive and not os.path.exists(archive_file):
        print(f"{archive_file} does not exist. Creating an empty {archive_file}.")
        open(archive_file, 'w').close()  # Create an empty file
    
    # Load archive.txt data, load it first to keep time stamps in order
    if (withArchive):    
        with open(archive_file, 'r') as f:
            data += f.readlines()

    # Load log.txt data
    with open(log_file, 'r') as f:
        data += f.readlines()

    return data

def feeding_amount_df(notes):
    match = re.search(r'(\d+)\s*mL', notes, re.IGNORECASE)
    return int(match.group(1)) if match else np.nan

# Master function to load daily stats
@app.route('/load_daily_stats', methods=['GET'])
def load_daily_stats():
    data = load_log_data(False)  # Load log data once
    data_df = convert_log_to_df(data)
    
    # Calculate summary counts for all count data
    today_df = data_df[data_df['date'] == datetime.today().date()]
    today_df_summary = today_df.loc[:,'dirty_diaper':'feeding_amt'].sum().to_frame(name='sum')
    
    # Calculate sleep statistics
    nap_count = today_df_summary.loc['nap_flag','sum']
    today_sleep_durations, still_sleeping = calculate_sleep_durations(today_df)
    
    if (today_sleep_durations is None):
        today_sleep_summary = 0
        time_since_nap = 0
        nap_count = 0
    else:
        today_sleep_summary = today_sleep_durations.loc[:,'sleep_duration'].sum()
        if still_sleeping:
            time_since_nap = 0
        else:
            time_diff = datetime.now().replace(second=0,microsecond=0) - today_sleep_durations.iloc[-1]['awake'] 
            time_since_nap = time_diff.total_seconds() / 60
    
    # Return all stats in one JSON response
    return jsonify({
        'wet_count': str(int(today_df_summary.loc['wet_diaper','sum'])),
        'dirty_count': str(int(today_df_summary.loc['dirty_diaper','sum'])),
        'time_since_nap': str(int(time_since_nap)),
        'nap_count': str(int(nap_count)),
        'total_nap_time': str(int(today_sleep_summary)),
        'feeding_count': str(int(today_df_summary.loc['feed_flag','sum'])),
        'total_feeding_amount': str(int(today_df_summary.loc['feeding_amt','sum']))
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
    
    if len(sleep_periods) == 0:
        return [None, False]
    
    # there is an off-by-one error, need to shift aslep windows down
    if sleep_periods.loc[0,'asleep'] > sleep_periods.loc[0,'awake']:
        if not pd.isna(sleep_periods.iloc[-1]['asleep']): # insert new row if needed
           sleep_periods = pd.concat([sleep_periods, pd.DataFrame({'asleep': [pd.NaT], 'awake': [pd.NaT]})], ignore_index=True)
        sleep_periods['asleep'] = sleep_periods['asleep'].shift(1)
     
    if (pd.isna(sleep_periods.iloc[-1]['awake'])):
        sleep_periods.at[sleep_periods.index[-1],'awake'] = datetime.now().replace(second=0,microsecond=0)
        still_asleep = True
    else:
        still_asleep = False
    
    sleep_periods['sleep_duration'] = (sleep_periods['awake'] - sleep_periods['asleep']).dt.total_seconds() / 60
    
    # Add additional helper columns: the date of the nap, the start time, and the end time
    sleep_periods.loc[:,'date'] = sleep_periods.loc[:,'asleep'].dt.date
    sleep_periods['asleep_time_min'] = sleep_periods['asleep'].dt.time
    sleep_periods['asleep_time_max'] = sleep_periods['awake'].dt.time
    
    return [sleep_periods, still_asleep]



# sleep_df = calculate_sleep_durations(log_df)[0]

def calculate_sleep_histogram(sleep_df):
    # Calculate th number of days in the dataset
    days_cnt = sleep_df['date'].nunique()
    
    sleep_record = []
    # Iterate over all rows of sleep_df
    for index, row in sleep_df.iterrows():
        time_asleep = floor_to_quarter_hour(sleep_df.loc[index,"asleep_time_min"])
        time_awake = floor_to_quarter_hour(sleep_df.loc[index,"asleep_time_max"])
        
        # print("index: " + str(index) +", time_asleep: " + str(time_asleep) + ", time_awake: " + str(time_awake))
        
        if (time_awake < time_asleep):
            before_midnight_seq = pd.date_range(str(time_asleep), "23:59", freq="15min").time
            after_midnight_seq = pd.date_range("00:00", str(time_awake), freq="15min").time
            time_range = list(before_midnight_seq) + list(after_midnight_seq)
        else:
            time_range = list(pd.date_range(str(time_asleep), str(time_awake), freq="15min").time)  # Generate time range for 15-minute increments
    
        sleep_record = sleep_record + time_range
    
    # group by the time string and do counts
    sleep_record_df = pd.DataFrame({"asleep_times":sleep_record})
    sleep_record_histogram = sleep_record_df.groupby("asleep_times").agg(time_counts = pd.NamedAgg(column="asleep_times", aggfunc="size")).reset_index()
    
    time_range = pd.date_range("00:00", "23:59", freq="15min").time  # Generate time range for 15-minute increments
    sleep_histogram_alltimes = pd.DataFrame({'asleep_times': time_range})  # Initialize sleep count to 0
    sleep_histogram_merged = sleep_histogram_alltimes.merge(sleep_record_histogram, on="asleep_times", how="left")
    sleep_histogram_merged['time_counts'] = sleep_histogram_merged['time_counts'].fillna(0).astype(int)
    
    sleep_histogram_merged['asleep_pct'] = sleep_histogram_merged['time_counts'] / days_cnt
            
    return sleep_histogram_merged


def plot_sleep_histogram(sleep_histogram_merged, ax):
     
    ax.plot(sleep_histogram_merged['asleep_times'].astype(str), sleep_histogram_merged['time_counts'], color='blue', alpha=0.7)

    ax.set_xlabel('Asleep Times')
    ax.set_xticks(ticks=range(0, len(sleep_histogram_merged['asleep_times']), 4), 
               labels=sleep_histogram_merged['asleep_times'].astype(str)[::4], rotation=45)
    
    ax.set_ylabel('Time Counts')
    ax.set_ylim(bottom=0)  # Y-axis minimum
    
    ax.grid(which='both', linestyle='--', linewidth=0.5, color='lightgray')
    
    three_hour_ticks = range(0, len(sleep_histogram_merged['asleep_times']), 12)  # Every 3 hours (12 x 15min)
    for tick in three_hour_ticks:
        ax.axvline(x=tick, color='gray', linewidth=1.5, linestyle = '--')  # Thicker line

    ax.set_title('Sleep Histogram - Time Counts by Asleep Times')
    
    return ax


def floor_to_quarter_hour(time_obj):
    # Extract hours and minutes
    hours = time_obj.hour
    minutes = time_obj.minute

    # Floor minutes to the nearest quarter-hour
    floored_minutes = (minutes // 15) * 15

    # Create a new time object with floored minutes
    floored_time = time(hour=hours, minute=floored_minutes)

    return floored_time


def calculate_daily_summary(reverse=True):
    # Step 1: Load all log data (including archive)
    log_data = load_log_data(withArchive=True)
    
    # Step 2: Convert log data to a DataFrame (which already includes the necessary columns)
    log_df = convert_log_to_df(log_data)
    
    # Step 3: Calculate sleep durations, get rid of overnight sleep
    log_df_sleep = calculate_sleep_durations(log_df)[0]
    log_df_sleep_filtered = log_df_sleep[log_df_sleep['asleep'].dt.date == log_df_sleep['awake'].dt.date].copy()
    
    
    # Step 4: Group by date and summarize the required fields
    log_summary = log_df.groupby('date').agg(
        wet_diapers_sum=pd.NamedAgg(column='wet_diaper', aggfunc='sum'),
        dirty_diapers_sum=pd.NamedAgg(column='dirty_diaper', aggfunc='sum'),
        all_feed_cnt=pd.NamedAgg(column='feed_flag', aggfunc='sum'),
        ).reset_index()
    
    feeding_summary = log_df[~log_df['feeding_amt'].isna()].groupby('date').agg(
           feeding_bottle_cnt = pd.NamedAgg(column = 'feeding_amt', aggfunc = 'size'),
           feeding_bottle_mean = pd.NamedAgg(column = 'feeding_amt', aggfunc = 'mean'),
           feeding_bottle_sum = pd.NamedAgg(column = 'feeding_amt', aggfunc = 'sum'),
           feed_amt_std = pd.NamedAgg(column='feeding_amt', aggfunc='std'),
           ).reset_index()

    sleep_summary = log_df_sleep_filtered.groupby('date').agg(
        naps_time_sum=pd.NamedAgg(column='sleep_duration', aggfunc='sum'),
        naps_time_cnt=pd.NamedAgg(column='sleep_duration', aggfunc='size'),
        naps_time_mean=pd.NamedAgg(column='sleep_duration', aggfunc='mean'),
        naps_time_std=pd.NamedAgg(column='sleep_duration', aggfunc='std')        
        ).reset_index()
    
    sleep_summary['naps_time_avg'] = sleep_summary['naps_time_sum'] / sleep_summary['naps_time_cnt']
    
    daily_summary = pd.merge(log_summary, sleep_summary, on='date', how='inner')
    daily_summary = pd.merge(daily_summary, feeding_summary, on='date', how='outer')
    
    if reverse:
        daily_summary = daily_summary.sort_values(by='date', ascending=False)

    # Return the final summary DataFrame
    return daily_summary

@app.route('/get_daily_summary', methods=['GET'])
def get_daily_summary():
    # Step 1: Get the daily summary using the calculate_daily_summary function
    daily_summary_df = calculate_daily_summary()
    daily_summary_df = daily_summary_df.fillna(0)
    # Step 2: Convert the DataFrame to a dictionary so it can be returned as JSON
    summary_data = daily_summary_df.to_dict(orient='records')
    return jsonify(summary_data)

@app.route('/plot_stats_graphs', methods=['GET'])
def plot_all_plots(num_days = 14):
    df = calculate_daily_summary(reverse=False).fillna(0)
    df_recent = df[df['date'] >= datetime.now().date() - timedelta(days = num_days)]
    dates = pd.to_datetime(df_recent['date'])
    wet_diapers = df_recent['wet_diapers_sum']
    dirty_diapers = df_recent['dirty_diapers_sum']
    
    # Nap data
    nap_lengths = df_recent['naps_time_mean']
    naps_time_sum = df_recent['naps_time_sum']
    naps_time_cnt = df_recent['naps_time_cnt']
    nap_err = df_recent['naps_time_std'] / np.sqrt(naps_time_cnt)
    
    # Feeding data
    bottle_feed_cnt = df_recent['feeding_bottle_cnt'].fillna(0)
    nonbottle_feed_cnt = df_recent['all_feed_cnt'] - bottle_feed_cnt
    bottle_feed_avg = df_recent['feeding_bottle_mean']
    bottle_feed_err = df_recent['feed_amt_std'] / np.sqrt(bottle_feed_cnt)
    
    
    fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(10, 10))
    
    # Step 1: Create a multi-panel figure (N-by-1)
    fig, axs = plt.subplots(nrows=4, ncols=1, figsize=(10, 10))  # 3 rows, 1 column

    # Step 2: Plot Diaper Stats on the first subplot
    axs[0].plot(dates, wet_diapers, '-o', label='Wet Diapers', color='blue')
    axs[0].plot(dates, dirty_diapers, '-o', label='Dirty Diapers', color='green')
    axs[0].set_title('Diaper Stats')
    axs[0].set_xlabel('Date')
    axs[0].set_ylabel('Count')
    axs[0].legend()
    axs[0].yaxis.grid()
    axs[0].set_xticks(dates)
    axs[0].set_xticklabels(dates.dt.strftime('%b %d'), rotation=45, ha="right")

    # Step 3: Plot Nap Lengths on the second subplot
    axs[1].errorbar(dates, nap_lengths, yerr=nap_err, fmt='-o', ecolor='gray', capsize=5, label='Average Nap Length', color='blue')
    axs[1].plot(dates, naps_time_sum, '-o', label='Total Nap Time', color='black')
    axs[1].set_title('Nap Lengths')
    axs[1].set_xlabel('Date')
    axs[1].set_ylabel('Time (minutes)')
    axs[1].legend()
    axs[1].yaxis.grid()
    axs[1].set_xticks(dates)
    axs[1].set_xticklabels(dates.dt.strftime('%b %d'), rotation=45, ha="right")
    
    # Step 4: plot feeding data, including number of feedings and average feeding amount
    axs[2].errorbar(dates, bottle_feed_avg, yerr = bottle_feed_err, fmt='-o', ecolor='gray', capsize=5, label='Average Bottle Amt', color='blue')
    axs[2].set_ylabel('Bottle Feeding Amount (mL)')
    axs[2].set_title('Feeding Data')
    
    ax3 = axs[2].twinx()
    bar_width = 0.4
    ax3.bar(dates, nonbottle_feed_cnt, width=bar_width, label='Non-bottle Feed Count', color='orange', alpha=0.6)
    ax3.bar(dates, bottle_feed_cnt, bottom=nonbottle_feed_cnt, width=bar_width, label='Bottle Feed Count', color='green', alpha=0.6)
    
    axs[2].set_xticks(dates)
    axs[2].set_xticklabels(dates.dt.strftime('%b %d'), rotation=45, ha="right")
    axs[2].legend(loc='upper left')  # For the bottle feeding average
    axs[2].grid(False)  # Disable grid on the stacked bar plot
    ax3.set_ylabel('Feeding Counts')  # Label for the right y-axis
    ax3.set_ylim(bottom=0)  # Ensure the y-axis starts at 0
    ax3.legend(loc='upper right')  # For the feeding counts
    
    log_data = load_log_data(True)
    log_data_df = convert_log_to_df(log_data)
    sleep_durations = calculate_sleep_durations(log_data_df)[0]
    sleep_histogram = calculate_sleep_histogram(sleep_durations)
    plot_sleep_histogram(sleep_histogram, axs[3])
    
    image_path = 'all_plots.png'  # Temporary location to store the plot
    # plt.subplots_adjust(hspace=0.5)
    plt.tight_layout()
    plt.savefig(image_path, format='png')
    plt.close()  # Close the plot to free up memory
    return send_file(image_path, mimetype='image/png')


if __name__ == '__main__':
    app.run()
