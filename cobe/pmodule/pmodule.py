import subprocess
import json
import sched, time
import psettings as ps
from dataclasses import asdict
import sys
sys.path.insert(1, 'C:\\Users\\David\\Desktop\\CoBe\\cobe\\rendering')
from renderingstack import RenderingStack
# from cobe.rendering.renderingstack import RenderingStack # doesn't work for some reason

class PModule(object):
    # GIT bash is not on the %PATH%, need to use full-path elicitation
    # https://stackoverflow.com/questions/57639971/running-a-simple-ls-command-with-subprocess-and-git-bash
    git_path = "C:\\Program Files\\Git\\bin\\bash.exe"
    tar_file_path = "/c/Users/David/Documents"
    output_path = "C:\\Users\\David\\Documents\\out.json"

    def __init__(self):
        navigation_command = "cd " + PModule.tar_file_path + "; "
        start_command =  navigation_command + "docker load -i docker_P-module.tar"
        run_main_command = navigation_command + "docker run --name contPP -t -d predpreyoriginal:latest sleep infinity"
        reset_command = navigation_command + "docker exec -it contPP sh reset.sh" # no longer requires the winpty for some reason

        # Create the RenderingStack object
        PModule.rendering_stack = RenderingStack()

        # Create the loop scheduler
        self.my_scheduler = sched.scheduler(time.time, time.sleep)
        self.consecutive_failures = 0

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
    
    def read_out_frame(self):
        with open(PModule.output_path) as file:
            json_file = json.load(file)

            # convert to the expected dictionary of dictionaries format
            newDict = {}
            for item in json_file["Prey"]:
                id = item["ID"]
                del item["ID"]
                newDict[id] = item

            json_file["Prey"] = newDict

            newDict = {}
            for item in json_file["Predator"]:
                del item["ID"]
                newDict[id] = item

            json_file["Predator"] = newDict

            serialized_json = json.dumps(json_file) + "\n"

            if not PModule.rendering_stack.send_message(serialized_json):
                self.consecutive_failures += 1
            else: 
                self.consecutive_failures = 0
    
    def start_loop(self):
        """Queues the first loop iteration and then begins execution"""
        self.my_scheduler.enter(ps.sending_frequency, 1, self.scheduled_send)
        self.my_scheduler.run()   

    def scheduled_send(self): 
        """The template for a single loop iteration: queues the next iteration and updates the data set"""
        # Schedule the next call first
        if self.consecutive_failures < ps.failure_limit:
            self.my_scheduler.enter(ps.sending_frequency, 1, self.scheduled_send)
            self.calculate_next_frame()
            self.read_out_frame()
        else:
            print("Consecutive failure limit reached, aborting queue")

p = PModule()
p.start_loop()