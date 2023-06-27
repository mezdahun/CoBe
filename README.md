# CoBe
Scientific demonstrator for showcasing collective behavior

## On-site Set-up
### Computer
Make sure the the power bar to the computer is switched off when the computer or affiliate equipment is not in use for security reasons.

On the Desktop are three folders to take note of:
1. CoBe: The active codebase for the installation, containing PModule, rendering stack, etc
2. CoBe-Unity: The codebase for the Unity applicatio, interacted with via the Unity Editor and VSCode
3. Test-Build: The location of the built Unity application

### Projectors
For the physical on-site set-up at TU, the projectors still need to be turned on and off manually. The projectors should always be disturbed as LITTLE as possible, otherwise the projection mapping will be thrown off completely.

There is a table next to one tower, and a cabinet next to the other than can be scaled to get to the projectors' on/off buttons. Note that these structures are intentionally positioned to not be physically in contact with the towers (so that climbing onto them doesn't disturb the tower structure and associatively, the projector).

- To turn on a projector, click the power button once.
- To turn off a projector, click the power button twice (with maybe a half-second delay between presses).

## Use of Rendering Stack and PModule
The functional code to run the installation up to its current level of deployment (22.06.2023) is located in the samplerun.py file. There are four methods which together launch the entire stack.

The standard process would be to run them sequentially as required; start --> project --> remove --> stop. This sample process is commented out at the bottom of the file.

To open and operate the file, one can:
1. Open VSCode (it's pinned to the task bar)
2. Once open, if the opened workspace is CoBe-Workspace (seen at the top of the VSCode window in the search bar, or at the top of the Explorer panel on the left), move on to step 4.
3. If not, using the top bar, navigate to file --> open recent --> CoBe-Workspace (Workspace)
4. Select the samplerun.py file from the explorer window on the left of the VSCode window
5. Comment or uncomment the methods at the bottom of the script as desired
6. Run the script using the play icon at the top right of the VSCode window (it only appears in scripts that can run, and so doesn't show up for this README if viewed in VSCode)
7. Repeat steps 5. and 6. as desired, just be sure to call the stop_everything() method when done, or the docker will keep generating files without clearing them

### start_everything()
The method will first open the apps relevant to the rendering stack if they are not already open/running, as listed in the rendersettings.py file under the file paths of the unity_path and resolume_path variables. It will then move onto the PModule and start all relevant processes for that as well, as dictated by the variables in the pmodulesettings.py file.

** Note that string file paths for Windows require double backslashes to escape the single slash from the string. String file paths for Linux-based machines use forward slashes.

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

These layer are mixed together, and their individual opacities can be controlled by playing with the layer's respective "V" slider (in green).

** Note that if you open both the Unity build AND the Unity editor at the same time, there will be two Spout Senders active (one from each app) which will confuse and break the channel in Resolume. To fix this if it happens, close both Unity applications and Resolume, and then restart the process ensuring only one Unity app is active. 

### Projection Mapping
To correct the projection mapping alignments of the border, one must navigate to the top-bar, output --> advanced, opening the advanced mapping menu. On the far left, we see the individual projectors and the slices for each projector. Along the top, we see the input and output tabs.
    Input: The slices that each respective projector sees. This can be made explicit by clicking on the slices under each projector headed in the left-most menu
    Output: How these slices should be transformed or rotated according to our needs

#### Workflow for Projection Mapping
1. Input slices are probably fine
2. Navigate to the output tab
3. For each slice, disable the "soft edge" radio button: this will disable edge blending so that you can see the full image from each projector, and accordingly, see the full mismatch
4. Use the project_image() method from the CoBe codebase to display an image for calibration, such as a grid, or a series of circles (so that you can also see the localized mismatches)
5. Choose a slice to work with from the menu on the left, and click on it
6. Use the output tools along the top bar: "Edit Points" or "Transform" to realign the chosen slice as desired. Transforms are really simple and effective for scaling, but for everything else, the magic really happens within the "Edit Points" menu
    6.1. Click the Edit Points button on the top bar
    6.2. Click on a node of the projected arena and move it at random with the mouse while looking at the projection on the floor to see which corner you're dragging (to orient yourself). Undo with ctrl + z after.
    6.3. Find your way to the area of the floor projection you're interested in by repeating step 6.2) until you find the closest node
    6.4. Alter the mapping by dragging and dropping the node with the mouse directly, as desired, or click on the node and make more fine-tuned changes with the +/- buttons of the X and Y fields of the Warping menu. Note that these fields only appear in the menu if a node is selected, and are specific to that node
    6.5. If the changes to a given node cause mapping issues in another area of the projection, maybe an additional nodal subdivision is necessary. This can be controlled by manipulating the "Subdivisions X" and "Subdivisions Y" fields of the Warping menu
7. When finished, press the "Save & Close" button at the bottom right of the window
8. Changes will be applied

## Loading a new PModule
Loading a new PModule is not quite as simple as changing a couple of file paths unfortunately, as the Unity app will also need to be rebuilt to reflect the new docker output folder location it should read from.

After saving the new PModule version to a location:
1. Open the CoBe codebase's pmodulesettings.py file (location: C:\Users\David\Desktop\CoBe\cobe\settings\pmodulesettings.py)
2. Alter the variable definitions of the first five variables in the file according to the new construction: 
    1. root_folder
    2. output_folder
    3. tar_file
    4. root_folder_on_container
    5. docker_image_name
3. Save and close
4. Open the RenderSettings.cs file (location: C:\Users\David\Desktop\CoBe-Unity\Assets\Scripts\RenderSettings.cs)
5. Change the folder_path variable to hold the same location as the output_folder variable in the pmodulesettings.py file (as changed in step 2.ii.)
6. Save and close
7. Delete everything in the Test-Build folder (location: C:\Users\David\Desktop\Test-Build)
8. Open the Unity Editor (pinned to the task bar) and select the CoBe-Unity project
9. Using the top bar of the Unity Editor window, navigate to File --> Build Settings
10. Verify that the Scenes/Main checkbox is checked at the top of the pop-up window, and nothing else (if there even are other options)
11. At the bottom right, click the "build" button, and then select the Test-Build folder
12. After the build has completed, close the Unity Editor
13. The transition is complete