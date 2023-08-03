# Path to the Unity application (Only implemented on Windows)
import os

# todo: Create a unified project folder instead of this scattered system
# Unity parameters
unity_app_executable_name = "CoBe.exe"
unity_app_path = "C:\\Users\\David\\Desktop\\Test-Build"

# Resolume parameters
resolume_app_executable_name = "Arena.exe"
resolume_path = "C:\\Program Files\\Resolume Arena"

# Deducted paths
unity_path = os.path.join(unity_app_path, unity_app_executable_name)
resolume_path = os.path.join(resolume_path, resolume_app_executable_name)

# TCP info
ip_address = "127.0.0.1"  # IP for TCP connection to listen on
port = 13000              # Port for TCP connection to listen on

# Other
start_up_delay = 3