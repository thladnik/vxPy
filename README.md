# MappApp
Multiprocess based software for visual stimulation and recording/online-analysis of behavior

## Usage
See the [wiki pages](https://github.com/thladnik/MappApp/wiki)

## Installation

### Windows (Anaconda recommended)

*Windows 10 is recommended*

1. Download and install the latest release of [Anaconda](https://www.anaconda.com/distribution/) (recommended for beginners) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html).
2. Import environment from conda_env.yml 
## Running the application
 
Either run from IDE configured with mappapp environment by running `__init__.py`

Or use Anaconda Command Prompt (Start >> Anaconda Prompt)
1. Go to the directory to which you've downloaded/cloned MappApp with `cd path\to\mappapp`
2. Activate the environment with `conda activate mappapp`
3. EITHER run MappApp with `python __init__.py`
    * This will prompt a UI where you can create your own program configuration
4. OR if a pre-configured INI file is available
    * Make sure it is located in the `./configs` folder and instead use `python __init__.py ini=filename.ini` 


## Dev info
### Import guidelines
These suggestions or guidelines for programming different new components, like processing routines or UI addons, aim to avoid circular imports and namespace clashes. 
They also make the code more intuitive to read and easier to maintain.
* For root-level modules, by convention, always import without the package path
    * Wrong
       ```
       import mappapp.IPC
       import mappapp.Def
       ```
    * Correct 
       ```
       from mappapp import IPC
       from mappapp import Def
       ```
    * **Never** import components from root-level modules directly, so **no** `from mappapp.IPC import Camera`, this will most likely end in exceptions
* For imports from **core modules**, always import individual components and **never** the whole module
    * Wrong
    
      ```
      from core import process
      process.AbstractProcess.register_rpc_callback(...)
      
      from core import routine
      class MyCustomRoutine(routine.CameraRoutine)
      ```
    * Correct
      ```
      from core.process import AbstractProcess
      AbstractProcess.register_rpc_callback(...)
      
      from core.routine import CameraRoutine
      class MyCustomRoutine(CameraRoutine)
      ```
* For imports of **process submodules**, always import the whole process module
    * Wrong
      ```
      from mappapp.process import Controller
      Controller.start_recording(...)
      ```
    * Correct
      ```
      from mappapp import process
      process.Controller.start_recording(...)
      ```

* For imports from non-core and non-root modules, you may either import the whole module or individual components. Try to keep paths within the program short. So avoid behemoths like `mappapp.gui.display.defaults.EyePositionDetector.set_threshold`
* Be aware, though, that module names may be duplicated. For example, all submodules in `mappapp.gui` may contain a `defaults` module (like `mappapp.gui.camera.defaults` or `mappapp.gui.display.defaults` )
