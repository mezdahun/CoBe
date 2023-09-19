"""All methods to implement TinyFlux databse daemon consuming json files and organizing them into db csv holder"""

import os
import json
import time
from datetime import datetime
import logging

from tinyflux import TinyFlux, Point

from cobe.settings import logs, pmodulesettings, database

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
    if not len(os.listdir(dp_input_path)) > 3:
        logging.debug(f"Database input folder {dp_input_path} is empty")
        return None

    # read all files in folder with json
    raw_dict = {}
    # getting the filename of the newest json file in the folder
    newest_file = max([os.path.join(dp_input_path, f) for f in os.listdir(dp_input_path) if f.endswith(".json") and os.access(os.path.join(dp_input_path, f), os.R_OK) and os.path.isfile(os.path.join(dp_input_path, f))],
                        key=os.path.getctime)
    logger.debug(f"Newest json file in folder is {newest_file}")

    logger.debug(f"Found the following files: \n{os.listdir(dp_input_path)}")

    # for fi, file in enumerate(os.listdir(dp_input_path)):
    while len(os.listdir(dp_input_path)) > 3:
        file = os.listdir(dp_input_path)[0]
        logger.debug(f"Checking file {file}, is newest={os.path.join(dp_input_path, file) == newest_file}")
        filename, file_extension = os.path.splitext(file)

        if file_extension == ".json" and os.path.join(dp_input_path, file) != newest_file:
            logger.debug(f"Consuming file {file}")
            if os.path.isfile(os.path.join(dp_input_path, file)) and os.access(os.path.join(dp_input_path, file), os.R_OK):
                try:
                    with open(os.path.join(dp_input_path, file), "r") as f:
                        input_data = json.load(f)
                        timestep = input_data["Step"]
                        timestamp = datetime.now()
                        raw_dict[timestep] = {}
                        # looping through all prey and filling the raw_dict
                        xs = []
                        ys = []
                        for prey in input_data["Prey"]:
                            id = prey["ID"]
                            if id > 50:
                                pass
                            else:
                                x = round(prey["x0"], precision)
                                y = round(prey["x1"], precision)
                                xs.append(x)
                                ys.append(y)
                                raw_dict[timestep][f"x{id}"] = x
                                raw_dict[timestep][f"y{id}"] = y

                        # calculating center of mass
                        COM = [round(sum(xs)/len(xs), precision), round(sum(ys)/len(ys), precision)]
                        raw_dict[timestep][f"COMx"] = COM[0]
                        raw_dict[timestep][f"COMy"] = COM[1]

                        # filling up with predators
                        for predator in input_data["Predator"]:
                            id = predator["ID"]
                            raw_dict[timestep][f"prx{id}"] = round(predator["x0"], precision)
                            raw_dict[timestep][f"pry{id}"] = round(predator["x1"], precision)
                        # add read timestamp
                        raw_dict[timestep]["timestamp"] = timestamp

                    # delete file after reading
                    os.remove(os.path.join(dp_input_path, file))
                    logger.debug(f"File {file} deleted")

                except Exception as e:
                    logger.error(f"Error while reading file {file}: {e}")
        else:
            logger.debug(f"File {file} is not a json file or is the newest file, skipping...")


    logging.debug("Read files into raw dicitonary, forwarding to database writer...")
    return raw_dict


def database_daemon_process(db_input_folder, with_wiping_input_folder=False, COM_queue=None, predator_queue=None):
    """Daemon process that reads the database input folder and writes the data into the database"""
    # deleting all files in input folder if requested
    if with_wiping_input_folder:
        for file in os.listdir(db_input_folder):
            try:
                os.remove(os.path.join(db_input_folder, file))
            except Exception as e:
                logger.error(f"Error while deleting file {file}: {e}")
        logger.info(f"Deleted all files in database input folder {db_input_folder} before starting daemon")

    # creating database first with run_id
    shard_id = 0
    db_timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    run_id = f"DB_{db_timestamp}_{shard_id}"
    db_path, db = create_database(run_id)

    wrote_datapoints = 0
    time_last_health = datetime.now()
    time_last_autopilot = datetime.now()
    time_last_db_push = datetime.now()
    health_freq = database.health_freq
    autopilot_freq = database.autopilot_freq
    db_push_freq = database.db_push_freq
    t = 0
    while True:
        # check if new files are in the database input folder
        raw_dict = check_db_input_folder(db_input_folder)
        if raw_dict is not None:
            # write raw_dict into database
            for timestep, fields in raw_dict.items():
                # read and remove timestamp from fields
                timestamp = fields.pop("timestamp")

                com = [[fields.pop("COMx"), fields.pop("COMy")]]
                fields["ts"] = int(timestep)
                p = Point(
                    time=timestamp,
                    fields=fields
                )

                if (timestamp - time_last_db_push).seconds >= db_push_freq:
                    db.insert(p, compact_key_prefixes=True)

                if t % 2 == 0:
                    if COM_queue is not None:
                        COM_queue.put(com)
                    if predator_queue is not None:
                        num_predators = pmodulesettings.num_predators
                        predators = []
                        for pi in range(num_predators):
                            predators.append([fields[f"prx{pi}"], fields[f"pry{pi}"]])
                        predator_queue.put(predators)
                # time_last_autopilot = datetime.now()

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
        t += 1
