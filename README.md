# CoBe
Scientific demonstrator for showcasing collective behavior

## Use of Rendering Stack and PModule
The functional code to run the installation up to its current level of deployment (22.06.2023) is located in the samplerun.py file. There are four methods which together launch the entire stack.

The standard process would be to run them sequentially as required; start --> project --> remove --> stop. This sample process is commented out at the bottom of the file.

### start_everything()
The method will first open the apps relevant to the rendering stack if they are not already open/running, as listed in the rendersettings.py file under the file paths of the unity_path and resolume_path variables. It will then move onto the PModule and start all relevant processes for that as well, as dictated by the variables in the pmodulesettings.py file.

Note that string file paths for Windows require double backslashes to escape the single slash from the string. String file paths for Linux-based machines use forward slashes.

### stop_everything()
The method will terminate the apps associated with the rendering stack if they are open (Unity and Resolume) and the PModule (Docker), as well as associated processes for both, such as stopping and removing the Docker container.

### project_image()
Will overlay the image at the file_path specified in the rendersettings.py image_file_path variable, overtop the Unity Render. Note that the render will continue in the background, it won't pause.

The image formats that have been tested are .png, .jpg, and .jpeg. The image resolution that's expected is square, and 4k (3840 x 3840 pixels). If the image is smaller than this resolution, it will not fill out the entire field of view. If the image is larger, parts of the image will be beyond view. Subsequent calls of this method will replace the existing displayed image if there is one with the new image.

** Note that project_image() and remove_image() methods should not be called in quick succession, as this will break Unity's TCP Listener. If this happens, the Python terminal will repeatedly state "TCP connection was refused, sleeping 2s and trying again". If this happens, correct the issue by ctrl + c in the terminal to stop the script, and then restart Unity and it should run thereafter without issue.

### remove_image()
Will remove any displayed image, if there is one, or do nothing otherwise.

** Note that project_image() and remove_image() methods should not be called in quick succession, as this will break Unity's TCP Listener. If this happens, the Python terminal will repeatedly state "TCP connection was refused, sleeping 2s and trying again". If this happens, correct the issue by ctrl + c in the terminal to stop the script, and then restart Unity and it should run thereafter without issue.

## Resolume
Resolume uses layers which when added together, create a composition, which is the final output. Currently:
    Layer 2: SpoutSender --> The Unity output
    Layer 1: Drone footage of water

These layer are mixed together, and their individual opacities can be controlled by playing with the layer's respective "V" slider (in green)

### Projection Mapping
To correct the projection mapping alignments of the border, one must navigate to the top-bar, output --> advanced, opening the advanced mapping menu. On the far left, we see the individual projectors and the slices for each projector. Along the top, we see the input and output tabs.
    Input: The slices that each respective projector sees. This can be made explicit by clicking on the slices under each projector headed in the left-most menu
    Output: How these slices should be transformed or rotated according to our needs

#### Workflow for Projection Mapping
1) Input slices are probably fine
2) Navigate to the output tab
3) For each slice, disable the "soft edge" radio button: this will disable edge blending so that you can see the full image from each projector, and accordingly, see the full mismatch
4) Use the project_image() method from the CoBe codebase to display an image for calibration, such as a grid, or a series of circles (so that you can also see the localized mismatches)
5) Choose a slice to work with from the menu on the left, and click on it
6) Use the output tools along the top bar: "Edit Points" or "Transform" to realign the chosen slice as desired. Transforms are really simple and effective for scaling, but for everything else, the magic really happens within the "Edit Points" menu
    6.1) Click the Edit Points button on the top bar
    6.2) Click on a node of the projected arena and move it at random with the mouse while looking at the projection on the floor to see which corner you're dragging (to orient yourself). Undo with ctrl + z after.
    6.3) Find your way to the area of the floor projection you're interested in by repeating step 6.2) until you find the closest node
    6.4) Alter the mapping by dragging and dropping the node with the mouse directly, as desired, or click on the node and make more fine-tuned changes with the +/- buttons of the X and Y fields of the Warping menu. Note that these fields only appear in the menu if a node is selected, and are specific to that node
    6.5) If the changes to a given node cause mapping issues in another area of the projection, maybe an additional nodal subdivision is necessary. This can be controlled by manipulating the "Subdivisions X" and "Subdivisions Y" fields of the Warping menu
7) When finished, press the "Save & Close" button at the bottom right of the window
8) Changes will be applied
