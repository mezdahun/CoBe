"""All methods to implement TinyFlux databse daemon consuming json files and organizing them into db csv holder"""

import os
import json
import time
from datetime import datetime
import logging

from tinyflux import TinyFlux, Point

from cobe.settings import logs

# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("database")


def create_database(filename):
    """Create a database with the given filename in the data folder under cobe root"""

    logging.info("Creating database...")
    # path of current file
    file_path = os.path.dirname(os.path.realpath(__file__))
    # path of current directory
    dir_path = os.path.dirname(file_path)
    # path of parent directory
    root_path = os.path.dirname(dir_path)
    save_path = os.path.join(root_path, "data", "database")

    # create folder if it doesn't exist
    if not os.path.exists(save_path):
        logging.info(f"Creating folder {save_path}")
        os.makedirs(save_path, exist_ok=True)

    # create database
    db_path = os.path.join(save_path, f"{filename}.csv")
    db = TinyFlux(db_path)

    logging.info(f"Database created at {db_path}")
    return db_path, db


def check_db_input_folder(dp_input_path, precision=4):
    """Checks the database input folder for new files and reads them into a raw dictionary.
    returns either the dictionary of read elements or None if no new files were found"""
    # check if folder exists
    if not os.path.exists(dp_input_path):
        raise FileNotFoundError(f"Database input folder {dp_input_path} does not exist")

    # check if folder is empty
    if not os.listdir(dp_input_path):
        logging.debug(f"Database input folder {dp_input_path} is empty")
        return None

    # read all files in folder with json
    raw_dict = {}
    for file in os.listdir(dp_input_path):
        filename, file_extension = os.path.splitext(file)
        logger.debug(f"Reading file {file}")
        if file_extension == ".json":
            with open(os.path.join(dp_input_path, file), "r") as f:
                input_data = json.load(f)
                timestep = input_data["Step"]
                timestamp = datetime.now()
                raw_dict[timestep] = {}
                # looping through all prey and filling the raw_dict
                for prey in input_data["Prey"]:
                    id = prey["ID"]
                    if id > 50:
                        pass
                    else:
                        raw_dict[timestep][f"x{id}"] = round(prey["x0"], precision)
                        raw_dict[timestep][f"y{id}"] = round(prey["x1"], precision)
                # filling up with predator (ONLY ONE PREDATOR)
                predator = input_data["Predator"][0]
                raw_dict[timestep]["prx"] = round(predator["x0"], precision)
                raw_dict[timestep]["pry"] = round(predator["x1"], precision)
                # add read timestamp
                raw_dict[timestep]["timestamp"] = timestamp

            # delete file after reading
            os.remove(os.path.join(dp_input_path, file))
            logger.debug(f"File {file} deleted")

        logging.debug("Read files into raw dicitonary, forwarding to database writer...")
        return raw_dict


def database_daemon_process(db_input_folder):
    """Daemon process that reads the database input folder and writes the data into the database"""
    # creating database first with run_id
    shard_id = 0
    db_timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    run_id = f"DB_{db_timestamp}_{shard_id}"
    db_path, db = create_database(run_id)

    wrote_datapoints = 0
    time_last_health = datetime.now()
    health_freq = 10
    while True:
        # check if new files are in the database input folder
        raw_dict = check_db_input_folder(db_input_folder)
        if raw_dict is not None:
            # write raw_dict into database
            for timestep, fields in raw_dict.items():
                # read and remove timestamp from fields
                timestamp = fields.pop("timestamp")
                fields["ts"] = int(timestep)
                p = Point(
                    time=timestamp,
                    fields=fields
                )
                db.insert(p, compact_key_prefixes=True)
            logger.debug(f"Raw dictionary written into database {run_id}")
            wrote_datapoints += len(raw_dict)

        if (datetime.now() - time_last_health).seconds >= health_freq:
            logger.info(f"Health: Wrote {wrote_datapoints} datapoints in {run_id} in the last {health_freq} seconds")
            wrote_datapoints = 0
            time_last_health = datetime.now()

        if os.path.getsize(db_path) / 1000000000 >= 1:
            logger.warning(f"Database {run_id} is larger than 1GB, creating new database...")
            shard_id += 1
            run_id = f"DB_{db_timestamp}_{shard_id}"
            db_path, db = create_database(run_id)
            logger.info(f"New database created: {db_path}")

        time.sleep(0.01)
