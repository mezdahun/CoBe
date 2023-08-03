import psutil
import os


def is_process_running(name: str) -> int:
    """Checks if a process is running on the system by comparing the name of each running process"""
    for pid in psutil.pids():
        try:
            p = psutil.Process(pid)
            if p.name() == name:
                # process found
                return pid
        except ProcessLookupError as e:
            print(f"ProcessLookupError while checking PIDs for running processes; {e}")
            print("This error needs further investigation")

            next

            # It seems like in some edge cases the PID can terminate between identifying the PID 
            # and calling its name via p.name(). In such cases we should just continue to evaluate 
            # the rest of the list.
        except psutil.NoSuchProcess as e:
            print(f"psutil.NoSuchProcess while checking PIDs for running processes; {e}. It seems the PID terminated between identification and attribution.")
            next
        except Exception as e:
            print(f"Unexpected error of type {type(e)} while checking PIDs; {e}")

    return 0

def clear_directory(file_path: str):
    """Clears the volume folder of .json files"""
    filelist = [f for f in os.listdir(file_path) if f.endswith(".json")]
    for f in filelist:
        try:
            os.remove(os.path.join(file_path, f))
        except:
            print("Error clearing the volume of .json files")
