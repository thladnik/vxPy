
<img align="right" width="140" height="140" src="vxpy/vxpy_icon.svg">

# vxPy

Multiprocess based software for vision experiments in Python

## Requirements

vxPy has been tested on Windows 10 and Ubuntu 20.04 LTS. It requires Python 3.8+

## Installation

### Installing Python

#### Windows
Download and install the Python 3.8+ binaries if not already installed from https://www.python.org/downloads/

#### Ubuntu

Install from canonical 
```console
user@machine: ~$ sudo apt-get install python3.x 
```

### Install vxPy with PyCharm (recommended)

TODO

### Install vxPy with terminal

#### Linux

Create a new folder where you'd like to install the vxPy application (here ~/vxPy_app/)
Using a terminal, create a virtual environment inside the empty folder 
```console
user@machine: ~/vxPy_app$ python3.x -m venv venv 
```

Activate the environment
```console
user@machine: ~/vxPy_app$ ./venv/bin/activate
```

Install vxPy with all its dependencies
```console
(venv) user@machine: ~/vxPy_app$ pip install git+https://github.com/thladnik/vxpy.git
```

Run vxPy setup to create application structure
```console
(venv) user@machine: ~/vxPy_app$ python -m vxpy setup
```
Alternatively, you can forego downloading sample files 
```console
(venv) user@machine: ~/vxPy_app$ python -m vxpy setup nosamples
```
**WARNING**: the demonstration in default.ini requires the sample files to run properly

You can run the default configuration with
```console
(venv) user@machine: ~/vxPy_app$ python main.py
```

## Compatible devices

### TheImagingSource (TIS) cameras
Under Windows [TIS](https://www.theimagingsource.de/) cameras are supported out of the box, using the TIS' original `tisgrabber` DLLs and their `ctype` bindings included in vxPy.

In order to use TIS cameras under Linux, you need to install `tiscamera` ([Github repository](https://github.com/TheImagingSource/tiscamera)) by following the instructions there. 

Within the Python environment, you then need to install `pycairo` and `PyGObject` with
```console
(venv) user@machine: ~/vxPy_app$ pip install pycairo PyGObject
```

**WARNING**: starting with version 1.0.0, `tiscamera` no longer supports older camera models (see list in repo). 
If you're using one of those, instead install the latest pre-1.0.0 stable release (0.14.0) by checking it out with
```console
user@machine: ~/tiscamera$ git checkout tags/v-tiscamera-0.14.0
```
directly after cloning the repository and before installing the dependencies or building the binaries.

### Basler cameras

[Basler](https://www.baslerweb.com/) cameras are supported for Windows and Linux. Just download the `pylon` installer for your plattform from the [Basler website](https://www.baslerweb.com/de/downloads/downloads-software/#type=pylonsoftware;language=all;version=all).

Then install the respective Python `pylon` package into your environment with
```console
(venv) user@machine: ~/vxPy_app$ pip install pypylon
```

### Arduino 

Arduino microcontrollers for analog and digital IO operations are supported natively (via standard Firmata). 

Coming soon: Instructions for setting up controller with Firmata.
