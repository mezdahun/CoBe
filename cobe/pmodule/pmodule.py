import json
import os
import subprocess
import logging

import cobe.settings.pmodulesettings as ps

from time import sleep
from cobe.tools.filetools import is_process_running, clear_directory
from cobe.settings import logs

# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger(__name__.split(".")[-1])


def entry_start_docker_container(batch_size=4, num_prey=50):
    """Starts the docker container of the Pmodule via command line
    :param batch_size: number of iterations carried out by the docker container in a given call
    :param num_prey: number of prey
    :return: does not return anything"""

    logger.info("Clearing PModule docker volume folder of .json files")
    clear_directory(f"{os.path.join(ps.root_folder, ps.output_folder)}")

    if not is_process_running("Docker Desktop.exe"):
        logger.info("Launching PModule Docker")
        subprocess.Popen(ps.docker_path)
        sleep(ps.docker_startup_timeout)
    else:
        logger.info("PModule Docker already running")

    continue_initialization = True

    # Check if any containers are actively using an image by the name of our target image
    # https://stackoverflow.com/questions/31288830/find-the-docker-containers-using-an-image
    containers_using_image = (subprocess.check_output(
        f'cmd /c \"docker container ls --all --filter=ancestor={ps.docker_image_name} --format \"{{{{.ID}}}}\"\"',
        shell=True)).splitlines()
    for container in containers_using_image:
        decoded_id = container.decode()
        if decoded_id:
            # If there are any, are those containers running?
            running_container_using_image = subprocess.check_output(
                f'cmd /c \"docker container inspect -f \'{{{{.State.Running}}}}\' {decoded_id}\"', shell=True)
            if running_container_using_image.decode().find('true'):
                # If so, then the PModule is already running, or a version of it is at least.
                logger.info("PModule is already running.")
                continue_initialization = False
                break

    if continue_initialization:
        logger.info("Loading PModule docker image")
        try:
            # First attempt to clear any image that exists by the same name
            os.system(f'cmd /c "docker image rm {ps.docker_image_name}"')
        except:
            logger.info("Couldn't remove PModule docker image, probably doesn't exist.")
            pass

        tar_path = os.path.join(ps.root_folder, ps.tar_file)
        if os.path.isfile(tar_path):
            os.system(f'cmd /c "docker load -i {tar_path}"')
        else:
            raise Exception("Docker image not found under path: " + tar_path)

        logger.info("Starting PModule docker container")
        # os.system(
        #     f'cmd /c "docker run --name {ps.docker_container_name} '
        #     f'-v {ps.root_folder}:{ps.root_folder_on_container} '
        #     f'-t -d {ps.docker_image_name} sh run.sh -b {batch_size} -n {num_prey}"')

        os.system(
            f'cmd /c "docker run --name {ps.docker_container_name} '
            f'-v {ps.root_folder}:{ps.root_folder_on_container} '
            f'-t -d {ps.docker_image_name} sh run.sh '
            f'-d {ps.sim_dt} '
            f'-o {ps.batch_size} '
            f'-M {ps.center_pull_radius} '
            f'-N {ps.num_prey} '
            f'-h {ps.repulsion_range} '
            f'-Y {ps.repulsion_steepness} '
            f'-H {ps.repulsion_strength} '
            f'-U {ps.distance_cutoff} '
            f'-A {ps.alignment_strength} '
            f'-F {ps.flee_strength} '
            f'-g {ps.flee_angle} '
            f'-s {ps.flee_steepness} '
            f'-i {ps.flee_range} '
            f'-D {ps.noise_strength} '
            f'-n {ps.num_predators}"')
        # todo: explicitly set the arena size in the container with pmodule settings and also add this when
        #       rescaling for projection stack. Magic numbers should go! Add all other simulation parameters for
        #       the PModule as well for transparency.


def entry_cleanup_docker_container():
    """Stops and removes the docker container of the Pmodule via command line"""
    logger.info("Clearing volume folder of .json files")
    clear_directory(f"{os.path.join(ps.root_folder, 'current')}")

    logger.info("Stopping PModule container...")
    os.system(f'cmd /c "docker kill {ps.docker_container_name}"')
    sleep(2)

    logger.info("Removing PModule container...")
    os.system(f'cmd /c "docker rm {ps.docker_container_name}"')


def generate_pred_json(position_list):
    """Generates a .json file containing the predator positions
    to be consumed by the Pmodule
    :param position_list: list of predator positions, e.g. [[x0, y0], [x1, y1], ...]
    Example:
    [
        {
            "ID": 0,
            "v0": -1.7511167168093489,
            "v1": -0.96622473789012819,
            "x0": 3000.305906020326201,
            "x1": -1000.859415112616865
        }
    ]
    """
    # generating filename with timestamp
    filename = ps.predator_filename

    id = None
    # generating list of predator dictionaries
    output_list = []
    for id, position in enumerate(position_list):
        if not ps.with_filtering_unrealistic:
            output_list.append({
                "ID": id,
                "v0": 0,
                "v1": 0,
                "x0": position[0],
                "x1": position[1]
            })
        else:
            # filtering unrealistic positions by checking the x and y coordinates of the detection
            # if the position is outside of the arena, the predator is not added to the list
            if abs(position[0]) < ps.max_abs_coord_detection and abs(position[1]) < ps.max_abs_coord_detection:
                output_list.append({
                    "ID": id,
                    "v0": 0,
                    "v1": 0,
                    "x0": position[0],
                    "x1": position[1]
                })
            else:
                logger.debug(f"Detected predator {id} is outside of the still realistic detection area, "
                             f"not adding to list")

    # todo: check if this was only necessary with more than 1 predators
    # filling list with dummy predators if necessary
    while len(output_list) < ps.num_predators:
        if id is None:
            print("No predators found, filling with dummy predators")
            print(f"output_list: {output_list}")
            id = 0
            position = [0, 0]
        output_list.append({
            "ID": id,
            "v0": 0,
            "v1": 0,
            "x0": position[0],
            "x1": position[1]
        })

    # writing to file with json.dump
    with open(os.path.join(ps.root_folder, filename), 'w') as f:
        json.dump(output_list, f)
