import os
from time import sleep

def entry_start_docker_container(batch_size=100, num_prey=5):
    """Starts the docker container of the Pmodule via command line
    :param batch_size: number of iterations carried out by the docker container in a given call
    :param num_prey: number of prey
    :return: does not return anything"""
    print("Starting P-module docker container")
    os.system(f'cmd /c "docker run --name cont -v //c/Users/David/Documents/predprey_batches://usr/src/myapp/batches -t -d predpreyoriginal:latest  sh run.sh -b {batch_size} -n {num_prey}"')

def entry_cleanup_docker_container():
    print("Stopping P-module container...")
    os.system('cmd /c "docker kill cont"')
    sleep(2)
    print("Removing P-module container...")
    os.system('cmd /c "docker rm cont"')