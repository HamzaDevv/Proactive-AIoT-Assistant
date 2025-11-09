import os
import time
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Define the scopes (what data you want to access).
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.activity.write',
    'https://www.googleapis.com/auth/fitness.blood_glucose.read',
    'https://www.googleapis.com/auth/fitness.blood_glucose.write',
    'https://www.googleapis.com/auth/fitness.blood_pressure.read',
    'https://www.googleapis.com/auth/fitness.blood_pressure.write',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.body.write',
    'https://www.googleapis.com/auth/fitness.body_temperature.read',
    'https://www.googleapis.com/auth/fitness.body_temperature.write',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.write',
    'https://www.googleapis.com/auth/fitness.location.read',
    'https://www.googleapis.com/auth/fitness.location.write',
    'https://www.googleapis.com/auth/fitness.nutrition.read',
    'https://www.googleapis.com/auth/fitness.nutrition.write',
    'https://www.googleapis.com/auth/fitness.oxygen_saturation.read',
    'https://www.googleapis.com/auth/fitness.oxygen_saturation.write',
    'https://www.googleapis.com/auth/fitness.reproductive_health.read',
    'https://www.googleapis.com/auth/fitness.reproductive_health.write',
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/fitness.sleep.write'
]

# The file token.json stores the user's access and refresh tokens.
TOKEN_FILE = 'token.json'
CREDS_FILE = 'credentials.json' # The file you downloaded from Google Console

def get_fit_service():
    """Builds and returns an authorized Google Fit service object."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('fitness', 'v1', credentials=creds)
        return service
    except HttpError as err:
        print(f"An error occurred building the service: {err}")
        return None

# --- GENERIC DATA FETCHING FUNCTION ---

def get_aggregated_data(service, start_time_millis, end_time_millis, data_type_name, data_source_id, output_filename, time_zone="Asia/Kolkata"):
    """
    Fetches aggregated data for a specific data type and saves it to a file.
    This is the best format for an LLM as it summarizes data by day.
    """
    try:
        aggregate_response = service.users().dataset().aggregate(
            userId='me',
            body={
                "aggregateBy": [{
                    "dataTypeName": data_type_name,
                    "dataSourceId": data_source_id
                }],
                "bucketByTime": {
                    "durationMillis": 86400000, # 86,400,000 ms = 1 day
                    "timeZoneId": time_zone  # Aligns buckets to local midnight
                },
                "startTimeMillis": start_time_millis,
                "endTimeMillis": end_time_millis
            }
        ).execute()
        
        print(f"\n--- Aggregated {data_type_name} Data (Daily) ---")
        json_output = json.dumps(aggregate_response, indent=2)
        print(json_output)

        with open(output_filename, 'w') as f:
            f.write(json_output)
        print(f"Successfully saved aggregated data to {output_filename}")
        return aggregate_response

    except HttpError as err:
        print(f"An error occurred querying for {data_type_name}: {err}")
        print("This may be because you have no data for this type or the dataSourceId is incorrect for your account.")
        return None

# --- DIAGNOSTIC FUNCTION ---
def list_all_data_sources(service):
    """Lists all data sources for the user and saves to a file."""
    try:
        sources_response = service.users().dataSources().list(userId='me').execute()
        print("\n--- All Available Data Sources ---")
        json_output = json.dumps(sources_response, indent=2)
        
        with open("all_my_data_sources.json", 'w') as f:
            f.write(json_output)
        print("Successfully saved all data sources to all_my_data_sources.json")
        return sources_response
    except HttpError as err:
        print(f"An error occurred listing data sources: {err}")
        return None

# --- HELPER FUNCTIONS FOR READING DATA ---

def fetch_step_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.step_count.delta",
        data_source_id="derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
        output_filename="fit_steps.json",
        time_zone=time_zone
    )

def fetch_heart_rate_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.heart_rate.bpm",
        data_source_id="derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm",
        output_filename="fit_heart_rate.json",
        time_zone=time_zone
    )

def fetch_sleep_data(service, start_millis, end_millis):
    # This method is different as it queries 'sessions'
    try:
        # Convert millis to nanos string format required by sessions API
        start_time_ns = f"{start_millis * 1_000_000}ns"
        end_time_ns = f"{end_millis * 1_000_000}ns"

        sleep_sessions = service.users().sessions().list(
            userId='me',
            startTime=start_time_ns,
            endTime=end_time_ns,
            activityType=72 # ActivityType 72 is 'Sleep'
        ).execute()

        print("\n--- Raw Sleep Session Data ---")
        json_output = json.dumps(sleep_sessions, indent=2)
        print(json_output)
        
        with open("fit_sleep.json", 'w') as f:
            f.write(json_output)
        print("Successfully saved sleep data to fit_sleep.json")
        return sleep_sessions
        
    except HttpError as err:
        print(f"An error occurred querying for SLEEP: {err}")
        return None


def fetch_weight_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.weight",
        data_source_id="derived:com.google.weight:com.google.android.gms:merge_weight",
        output_filename="fit_weight.json",
        time_zone=time_zone
    )

# --- NEW FUNCTIONS BASED ON YOUR DIAGNOSTIC FILE ---

def fetch_active_minutes_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.active_minutes",
        data_source_id="derived:com.google.active_minutes:com.google.android.gms:merge_active_minutes",
        output_filename="fit_active_minutes.json",
        time_zone=time_zone
    )

def fetch_calories_expended_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.calories.expended",
        data_source_id="derived:com.google.calories.expended:com.google.android.gms:merge_calories_expended",
        output_filename="fit_calories_expended.json",
        time_zone=time_zone
    )

def fetch_distance_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.distance.delta",
        data_source_id="derived:com.google.distance.delta:com.google.android.gms:merge_distance_delta",
        output_filename="fit_distance.json",
        time_zone=time_zone
    )

def fetch_heart_minutes_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.heart_minutes",
        data_source_id="derived:com.google.heart_minutes:com.google.android.gms:merge_heart_minutes",
        output_filename="fit_heart_minutes.json",
        time_zone=time_zone
    )

def fetch_height_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.height",
        data_source_id="derived:com.google.height:com.google.android.gms:merge_height",
        output_filename="fit_height.json",
        time_zone=time_zone
    )

def fetch_oxygen_saturation_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.oxygen_saturation",
        data_source_id="derived:com.google.oxygen_saturation:com.google.android.gms:merged",
        output_filename="fit_oxygen_saturation.json",
        time_zone=time_zone
    )

def fetch_speed_data(service, start_millis, end_millis, time_zone):
    # This ID was confirmed from your JSON file
    return get_aggregated_data(
        service=service,
        start_time_millis=start_millis,
        end_time_millis=end_millis,
        data_type_name="com.google.speed",
        data_source_id="derived:com.google.speed:com.google.android.gms:merge_speed",
        output_filename="fit_speed.json",
        time_zone=time_zone
    )

def fetch_location_data(service, start_millis, end_millis):
    """Fetches raw location data points."""
    DATA_TYPE_NAME = "com.google.location.sample"
    # This is a guess for the merged data source ID, as it wasn't in your file.
    DATA_SOURCE_ID = "derived:com.google.location.sample:com.google.android.gms:merge_location_sample"
    
    print(f"\n--- Fetching Raw {DATA_TYPE_NAME} Data ---")
    print("WARNING: Your diagnostic file did not show a location data source. This will likely be empty or fail.")
    
    try:
        # Format times in nanoseconds for the dataset ID
        start_ns = start_millis * 1_000_000
        end_ns = end_millis * 1_000_000
        dataset_id = f"{start_ns}-{end_ns}"

        # We query the raw data source directly
        dataset = service.users().dataSources().datasets().get(
            userId='me',
            dataSourceId=DATA_SOURCE_ID,
            datasetId=dataset_id
        ).execute()

        json_output = json.dumps(dataset, indent=2)
        print(json_output)
        
        with open("fit_location.json", 'w') as f:
            f.write(json_output)
        print("Successfully saved location data to fit_location.json")
        return dataset
        
    except HttpError as err:
        print(f"An error occurred querying for {DATA_TYPE_NAME}: {err}")
        print("This is expected if you do not have location tracking enabled or no data source exists.")
        return None

# --- EXAMPLE OF WRITING DATA ---

def get_or_create_data_source(service, data_type_name):
    """
    Creates a new data source for this script if it doesn't already exist.
    This is the proper way to write data.
    """
    # A unique identifier for your script
    DATA_SOURCE_ID = "raw:com.google.weight:com.mycompany.myscript:my_weight_input"
    
    try:
        # Check if the data source already exists
        service.users().dataSources().get(
            userId='me',
            dataSourceId=DATA_SOURCE_ID
        ).execute()
        print("Data source for writing weight already exists.")
    except HttpError as err:
        # If it doesn't exist (404), create it
        if err.resp.status == 404:
            print("Weight-writing data source not found, creating new one...")
            data_source_body = {
                "dataStreamName": "My Python Script Weight Input",
                "type": "raw",
                "application": {
                    "name": "My Python Script",
                    "version": "1.0"
                },
                "dataType": {
                    "name": data_type_name
                },
                "device": {
                    "type": "scale",
                    "manufacturer": "MyCompany",
                    "model": "Script v1",
                    "uid": "my-script-uid-123"
                }
            }
            try:
                service.users().dataSources().create(
                    userId='me',
                    body=data_source_body
                ).execute()
                print("Successfully created new data source for writing weight.")
            except HttpError as create_err:
                print(f"Error creating data source: {create_err}")
                return None
        else:
            print(f"Error checking data source: {err}")
            return None
            
    return DATA_SOURCE_ID

def log_new_weight_reading(service, weight_kg):
    """Logs a new weight reading to Google Fit."""
    
    DATA_TYPE_NAME = "com.google.weight"
    
    # Get or create the data source first
    data_source_id = get_or_create_data_source(service, DATA_TYPE_NAME)
    if not data_source_id:
        print("Could not get or create data source. Aborting weight log.")
        return

    # Get current time in nanoseconds
    now_ns = int(time.time() * 1_000_000_000)
    
    # Create a dataset patch
    dataset_body = {
        "minStartTimeNs": now_ns,
        "maxEndTimeNs": now_ns,
        "dataSourceId": data_source_id, # Use our script's unique ID
        "point": [
            {
                "startTimeNanos": now_ns,
                "endTimeNanos": now_ns,
                "dataTypeName": DATA_TYPE_NAME,
                "value": [
                    {
                        "fpVal": weight_kg
                    }
                ]
            }
        ]
    }

    try:
        # Use datasets.patch to add new data points
        service.users().dataSources().datasets().patch(
            userId='me',
            dataSourceId=data_source_id,
            datasetId=f"{now_ns}-{now_ns}", # A unique ID for this data point
            body=dataset_body
        ).execute()
        
        print(f"\nSuccessfully logged new weight: {weight_kg} kg")
        print("Note: It may take a few moments for this to appear in Google Fit.")
        
    except HttpError as err:
        print(f"An error occurred trying to WRITE weight data: {err}")


# --- MAIN FUNCTION (Modified for Data Fetching) ---
def main():
    service = get_fit_service()
    if not service:
        print("Could not get Google Fit service. Exiting.")
        return

    # --- REGULAR DATA FETCH (Re-enabled) ---
    # Set the time range for the data you want to fetch
    # We'll get data for the last 7 days
    end_time_millis = int(time.time() * 1000)
    start_time_millis = end_time_millis - (7 * 24 * 60 * 60 * 1000) # 7 days ago
    
    # Define your local time zone (IANA format)
    LOCAL_TIME_ZONE = "Asia/Kolkata"

    print(f"Fetching data from {start_time_millis} to {end_time_millis} using {LOCAL_TIME_ZONE} timezone...")

    # Call all the read functions that have data
    fetch_step_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_heart_rate_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_sleep_data(service, start_time_millis, end_time_millis) # Sleep uses a different method
    fetch_weight_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    
    # Call all the new functions
    fetch_active_minutes_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_calories_expended_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_distance_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_heart_minutes_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_height_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_oxygen_saturation_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)
    fetch_speed_data(service, start_time_millis, end_time_millis, LOCAL_TIME_ZONE)

    # Call the location function (will likely be empty)
    fetch_location_data(service, start_time_millis, end_time_millis)

    # Example of calling a write function
    # Uncomment the line below to log a new weight of 75.5 kg
    # log_new_weight_reading(service, 75.5)

    print("\n--- Data fetching complete. ---")


if __name__ == '__main__':
    main()