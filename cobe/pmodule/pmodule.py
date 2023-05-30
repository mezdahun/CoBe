import subprocess

class PModule(object):
    # GIT bash is not on the %PATH%, need to use full-path elicitation
    # https://stackoverflow.com/questions/57639971/running-a-simple-ls-command-with-subprocess-and-git-bash
    git_path = "C:\\Program Files\\Git\\bin\\bash.exe"
    tar_file_path = "/c/Users/David/Documents"

    def __init__(self):
        navigation_command = "cd " + PModule.tar_file_path + "; "
        start_command =  navigation_command + "docker load -i docker_P-module.tar"
        run_main_command = navigation_command + "docker run --name contPP -t -d predpreyoriginal:latest sleep infinity"
        reset_command = navigation_command + "docker exec -it contPP sh reset.sh" # no longer requires the winpty for some reason

        # load the .tar file
        output = subprocess.check_output([PModule.git_path, "-c", start_command])
        print(output.decode('utf-8').strip())

        # run the container
        try:
            # will likely fail
            output = subprocess.check_output([PModule.git_path, "-c", run_main_command]) 
        except subprocess.CalledProcessError:
            print("Failed to run script in docker, it's probably already running")
        
        # perform an instance reset to ensure we're starting fresh
        output = subprocess.check_output([PModule.git_path, "-c", reset_command])
        print(output.decode('utf-8'))

    def calculate_next_frame(self):
        # accepts prey data

        # run dockered p-module
        update_command = "docker exec -it contPP sh run.sh"
        output = subprocess.check_output([PModule.git_path, "-c", update_command])
        print(output.decode('utf-8').strip())

        # save it
        save_command = "docker cp contPP:/usr/src/myapp/out.json " + PModule.tar_file_path + "/out.json"
        output = subprocess.check_output([PModule.git_path, "-c", save_command])
        print(output.decode('utf-8').strip())

p = PModule()
for i in range(0, 10):
    p.calculate_next_frame()