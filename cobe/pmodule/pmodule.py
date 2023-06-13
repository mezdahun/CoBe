import os
from time import sleep
import psutil
import subprocess

root_folder = "C:\\Users\\David\\Documents\\predprey_batches"
docker_path = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"

def is_file_running(name: str) -> bool:
    for pid in psutil.pids():
        p = psutil.Process(pid)
        if p.name() == name:
            return True
    return False

def entry_start_docker_container(batch_size=4, num_prey=50):
    """Starts the docker container of the Pmodule via command line
    :param batch_size: number of iterations carried out by the docker container in a given call
    :param num_prey: number of prey
    :return: does not return anything"""

    print("Clearing volume folder of .json files")
    clear_directory(f"{root_folder}\\current")

    if not is_file_running("Docker Desktop.exe"):
        print("Launching Docker")
        subprocess.Popen(docker_path)
        sleep(10)
    else:
        print("Docker already running")

    print("Loading P-module docker image")
    try:
        # First attempt to clear any image that exists by the same name
        os.system(f'cmd /c "docker image rm predpreyoriginal:latest"')
    except:
        pass

    os.system(f'cmd /c "docker load -i {root_folder}\\docker.tar"')

    print("Starting P-module docker container")
    os.system(f'cmd /c "docker run --name cont -v {root_folder}://usr/src/myapp/batches -t -d predpreyoriginal:latest  sh run.sh -b {batch_size} -n {num_prey}"')

def entry_cleanup_docker_container():
    print("Clearing volume folder of .json files")
    clear_directory(f"{root_folder}\\current")

    print("Stopping P-module container...")
    os.system('cmd /c "docker kill cont"')
    sleep(2)

    print("Removing P-module container...")
    os.system('cmd /c "docker rm cont"')

def clear_directory(file_path: str):
    filelist = [ f for f in os.listdir(file_path) if f.endswith(".json") ]
    for f in filelist:
        try:
            os.remove(os.path.join(file_path, f))
        except:
            print("Error clearing the volume of .json files")


        
# entry_start_docker_container()
# entry_cleanup_docker_container()