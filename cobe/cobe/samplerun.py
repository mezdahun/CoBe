from cobe.rendering.renderingstack import RenderingStack
import cobe.pmodule.pmodule as pmodule
import cobe.settings.rendersettings as rs

class SampleRun():
    def __init__(self):
        self.rendering_stack = RenderingStack()

    def start_everything(self):
        self.rendering_stack.open_apps() # Opens the apps relevant to the rendering stack (Unity & Resolume)
        pmodule.entry_start_docker_container() # Starts Docker and begins running PModule in a container

    def stop_everything(self):
        self.rendering_stack.close_apps() # Closes the apps relevant to the rendering stack (Unity & Resolume)
        pmodule.entry_cleanup_docker_container() # Stops PModule and destroys its container

    def project_image(self):
        # Projects the image the file path listed in the rendersettings.py file
        with open(rs.image_file_path, "rb") as image:
            self.rendering_stack.display_image(image.read())        

    def remove_image(self):
        # Removes any image if there is one projected
        self.rendering_stack.remove_image()

sample = SampleRun() # Initialize an instance
# sample.start_everything() # starts everything
# sample.project_image() # projects image at filepath in rendersettings.py, expects 4k. Subsequent calls replace the existing image
# sample.remove_image() # removes any image that is currently displayed, if any
sample.stop_everything() # stops everything