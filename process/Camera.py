"""
MappApp ./process/Camera.py - Handles camera interaction and writes to the camera buffers.
Copyright (C) 2020 Tim Hladnik

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import cv2
import logging
import numpy as np
from time import perf_counter, strftime, sleep

import Config
import Controller
import Definition
import IPC
import Logging

if Definition.Env == Definition.EnvTypes.Dev:
    from IPython import embed

class Main(Controller.BaseProcess):
    name = Definition.Process.Camera

    _recording : bool                       = False

    def __init__(self, **kwargs):
        Controller.BaseProcess.__init__(self, **kwargs)

        ### Set camera buffer object
        IPC.BufferObject.constructBuffers()

        ### Set recording parameters
        self.frameDims = (int(Config.Camera[Definition.Camera.res_y]),
                          int(Config.Camera[Definition.Camera.res_x]))
        self.fps = Config.Camera[Definition.Camera.fps]

        ### Set up camera
        ## The Imaging Source cameras
        if Config.Camera[Definition.Camera.manufacturer] == 'TIS':
            import devices.cameras.tisgrabber as IC
            self.camera = IC.TIS_CAM()
            self.camera.open(Config.Camera[Definition.Camera.model])
            self.camera.SetVideoFormat(Config.Camera[Definition.Camera.format])
            self.camera.SetPropertySwitch("Framerate","Auto",0)
            self.camera.SetPropertySwitch("Exposure","Auto",0)
            self.camera.SetPropertyAbsoluteValue("Exposure", "Value", 1./1000)
            self.camera.SetFrameRate(self.fps)
            self.camera.SetContinuousMode(0)
            self.camera.StartLive(0)

        ## Virtual camera
        elif Config.Camera[Definition.Camera.manufacturer] == 'virtual':
            import devices.cameras.virtual as VC
            self.camera = VC.VirtualCamera()
            self.camera.setVideoFormat(Config.Camera[Definition.Camera.format],
                                       Config.Camera[Definition.Camera.res_y],
                                       Config.Camera[Definition.Camera.res_x])

        Logging.logger.log(logging.DEBUG, 'Using camera {}>>{}'
                           .format(Config.Camera[Definition.Camera.manufacturer],
                                   Config.Camera[Definition.Camera.model]))

        ### Run event loop
        self.run()

    def startVideoRecording(self):

        if not(self._recording):
            startt = strftime('%Y-%m-%d-%H-%M-%S')
            Logging.logger.log(logging.INFO, 'Start video recording at time {}'.format(startt))
            # Define codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.videoRecord = cv2.VideoWriter(
                'output_%s.avi' % startt, fourcc, self.fps,
                (self.frameDims[1], self.frameDims[0]), isColor=0)
            self._recording = True

            return
        Logging.logger.log(logging.WARNING, 'Unable to start recording, video recording is already on')

    def _writeFrame(self):

        if self._recording:
            frames = list()
            for i, name in enumerate(IPC.BufferObject.buffers()):
                if IPC.BufferObject.buffers()[name]._recordBuffer:
                    frames.append(IPC.BufferObject.readBuffer(name))
            self.videoRecord.write(np.hstack(frames))

    def stopVideoRecording(self):

        if self._recording:
            Logging.logger.log(logging.INFO, 'Stop video recording')
            self.videoRecord.release()
            self._recording = False

            return
        Logging.logger.log(logging.WARNING, 'Unable to stop recording, because there is no active recording')


    def _toggleVideoRecording(self):
        if self._recording:
            self.stopVideoRecording()
        else:
            self.startVideoRecording()

    def _updateBufferEvalParams(self, name, **kwargs):
        IPC.BufferObject.updateBufferEvalParams(name, **kwargs)

    def main(self):
        # Fetch current frame and update camera buffers
        frame = self.camera.GetImage()
        IPC.BufferObject.update(frame)
        # Write to file
        self._writeFrame()

        # Wait until next frame
        t = self.t + 1./self.fps - perf_counter()
        if t > 0.:
            sleep(t)


    def _startShutdown(self):
        if self._recording:
            self.stopVideoRecording()
        Controller.BaseProcess._startShutdown(self)
