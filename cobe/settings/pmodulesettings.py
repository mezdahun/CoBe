# folder to save batch json files on host
root_folder = "C:\\Users\\David\\Documents\\predprey_batches"
# foder to save batch json files on docker container
root_folder_on_container = "//usr/src/myapp/batches"

# path of docker executable on windows
docker_path = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"

# time to wait for docker to start up (s)
docker_startup_timeout = 10

# pmodule docker image name
docker_image_name = "predpreyoriginal:latest"