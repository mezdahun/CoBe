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

# path of docker executable on windows
docker_path = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"

# time to wait for docker to start up (s)
docker_startup_timeout = 10