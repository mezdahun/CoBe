import os
# folder on host where PModule is located
root_folder = "C:\\Users\\David\\Documents\\predprey_batches"

# name of output folder in root_folder
output_folder = "current"

# name of .tar file in root_folder
tar_file = "docker.tar"

# folder on docker container where batch json files are to be saved
root_folder_on_container = "//usr/src/myapp/batches"

# pmodule docker image name
docker_image_name = "predpreyoriginal:latest"

# pmodule docker container name
docker_container_name = "pmodule_container"

# path of docker executable on windows
docker_path = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"

# time to wait for docker to start up (s)
docker_startup_timeout = 10

# Inner coordinate system of the simulation
max_abs_coord = 20

# Filename for predator json file
predator_filename = "out_pred.json"

## P-module algorithm parameters
# -d Simulation step size
# -o Size of batches to run the simulation for
# -M Min. cluster size
# -N Amount of prey particles
# -h Repulsion range
# -Y Repulsion steepness
# -H Repulsion strength
# -U Distance Cutoff
# -A Alignment strength, how strongly prey align their velocity to neighbors
# -F Flee strength, how strongly do prey react to predator
# -g Flee angle, angle with which prey turn away from predator while fleeing
# -s Flee steepness, steepness of the flee angle
# -i Flee range, range from which prey react to predators
# -D Strength of the noise applied to particles
# -n Amount of predators
# -O Radius for pulling prey back to center

# default values
sim_dt = 0.02
batch_size = int(os.environ.get("PM_BATCH_SIZE", 8))           # thymios 1, stick - 6-8
center_pull_radius = float(os.environ.get("PM_CENTER_PULL_RADIUS", 20))  # thymios 17, stick - 20
num_prey = 50  #100
repulsion_range = 1
repulsion_steepness = -4
repulsion_strength = 2
distance_cutoff = 3
alignment_strength = 3
flee_strength = 50
flee_angle = 0.523599
flee_steepness = 1
flee_range = 10
noise_strength = 0.2
num_predators = int(os.environ.get("PM_NUM_PREDATORS", 1))        # single stick-1, multiplayer-2


