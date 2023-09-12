import numpy as np
import pandas as pd
from ngmt.utils.ngmt_data_classes import FileInfo, ChannelData, RecordingData
from datetime import datetime, timedelta
from ngmt.utils.file_io import get_unit_from_type


def import_polar_watch(data_file_path: str):
    raw = pd.read_csv(data_file_path)

    # Extract the basic information from the first row (athlete data)
    athlete_data = raw.iloc[0]
    athlete_info = FileInfo(
        TaskName=athlete_data["Name"],
        SamplingFrequency=np.nan,  # Not available in the athlete data
        TaskDescription=f"{athlete_data['Sport']} on {athlete_data['Date']} at {athlete_data['Start time']}",
    )

    # Drop the athlete data and remaining rows with NaN values
    df = raw.iloc[2:]

    # Create timestamps for the motion data
    start_time = pd.to_datetime(f"{athlete_data['Date']} {athlete_data['Start time']}")
    times_str = df["Sport"].to_list()
    times = [
        (
            datetime.strptime(time_str, "%H:%M:%S").hour * 3600
            + datetime.strptime(time_str, "%H:%M:%S").minute * 60
            + datetime.strptime(time_str, "%H:%M:%S").second
        )
        for time_str in times_str
    ]

    df = pd.read_csv(data_file_path, skiprows=[0, 1])  # Skip the first and second rows

    # Extract channel names
    channel_names = ["heart_rate", "walking_velocity", "position_from_start"]

    # Extract the time series data
    time_series = df[["HR (bpm)", "Speed (km/h)", "Distances (m)"]].values.T

    # Create ChannelMetaData objects for each channel
    channels = []
    for channel_name in channel_names:
        channel_data = ChannelMetaData(
            name=channel_name,
            component="n/a",
            ch_type="MISC",
            tracked_point="n/a",
            units="",
        )
        channels.append(channel_data)

    # Create the MotionData object
    motion_data = MotionData(
        info=athlete_info,
        times=times,
        channel_names=channel_names,
        time_series=time_series,
    )

    return motion_data


def import_hasomed_imu(file_path: str):
    """
    This function reads a file and returns a MotionData object.
    Parameters:
    file (str): path to the .csv file
    Returns:
    MotionData: an object of class MotionData that includes FileInfo object with metadata from the file,
    a 1D numpy array with time values, a list of channel names, and a 2D numpy array with the time series data.
    The file structure is assumed to be as follows:
    - The header contains lines starting with '#' with metadata information.
    - The actual time series data starts after the metadata lines.
    - The first column in the time series data represents the 'Sample number' or time.
    - The remaining columns represent the channel data.
    Note: This function only extracts a subset of the possible FileInfo fields. Additional fields need to be added manually
    depending on what fields are present in the files. Also, error checking and exception handling has been kept minimal for
    simplicity. You might want to add more robust error handling for a production-level application.
    """
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Keep track of where the metadata ends and the time series data begins
    data_start_idx = 0

    for idx, line in enumerate(lines):
        # Metadata ends when we encounter a line that doesn't start with '#'
        if not line.startswith("#"):
            data_start_idx = idx
            break

        # Extract fields for FileInfo
        parts = line.strip().split(";")

        if "Patient-ID" in line:
            SubId = parts[2]
        elif "Sample rate" in line:
            SamplingFrequency = float(parts[6])
        elif "Assessment type" in line:
            TaskName = parts[3]
        # Add more fields as necessary here...

    # Instantiate empty FileInfo
    info = FileInfo(
        SubjectID=SubId, TaskName=TaskName, DatasetName="ComOn", FilePath=file_path
    )  # default SamplingFrequency to 100.0 if not found

    # Create DataFrame from the time series data
    data = pd.read_csv(file_path, skiprows=data_start_idx - 1, delimiter=";")

    # Extract the channel names from the column names of the DataFrame
    channel_names = data.columns.tolist()

    # Convert time to numpy array
    times = np.linspace(0, data.shape[0] / SamplingFrequency, data.shape[0])

    # drop non relevant columns
    filtered_col_names = [
        col
        for col in channel_names
        if not any(sensor in col for sensor in ["Acc", "Gyro", "Mag"])
    ]
    channel_names = [
        col
        for col in channel_names
        if any(sensor in col for sensor in ["Acc", "Gyro", "Mag"])
    ]
    time_series = data.drop(columns=filtered_col_names).to_numpy().T  # transpose

    # Create ChannelData class
    ch_types = [["ACCEL"] * 3 + ["GYRO"] * 3 + ["MAGN"] * 3] * 3
    ch_types = [ch for sublist in ch_types for ch in sublist]

    tracked_point = [["0"] * 9, ["1"] * 9, ["6"] * 9]
    tracked_point = [ch for sublist in tracked_point for ch in sublist]

    units = get_unit_from_type(ch_types)

    channel_data = ChannelData(
        name=channel_names,
        component=["x", "y", "z"] * 6,
        ch_type=ch_types,
        tracked_point=tracked_point,
        units=units,
    )

    # Create RecordingData class
    test_data = RecordingData(
        name="HasoMedTest",
        data=data,
        sampling_frequency=SamplingFrequency,
        channels=channel_data,
        start_time=0.0,
        times=times,
        types=ch_types,
    )

    return test_data
