from cobe.rendering.renderingstack import RenderingStack
import cobe.pmodule.pmodule as pmodule
import cobe.settings.rendersettings as rs

class SampleRun():
    def __init__(self):
        self.rendering_stack = RenderingStack() # Starts Unity and Resolume

    def start_pmodule(self):
        pmodule.entry_start_docker_container() # Starts Docker and begins running PModule in a container

    def stop_pmodule(self):
        pmodule.entry_cleanup_docker_container() # Stops PModule and destroys its container

    def project_image(self):
        if self.rendering_stack:
            # Projects the image the file path listed in the rendersettings.py file
            with open(rs.image_file_path, "rb") as image:
                self.rendering_stack.display_image(image.read())        

    def remove_image(self):
        # Removes any image if there is one projected
        if self.rendering_stack:
            self.rendering_stack.remove_image()

# sample = SampleRun() # starts Unity and Resolume
# sample.start_pmodule() # starts PModule
# sample.project_image() # projects image, expects 4k. Subsequent calls replace the existing image
# sample.remove_image() # removes any image that is currently displayed, if any
# sample.stop_pmodule() # stops the PModule

# Resolume and Unity still need to be closed manually!