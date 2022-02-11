"""
vxPy ./devices/camera/tis_windows_tisgrabber.py
Copyright (C) 2022 Tim Hladnik

Based on TIS' tisgrabber usage examples for Python
at https://github.com/TheImagingSource/IC-Imaging-Control-Samples/

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
from typing import List, Tuple, Type
import ctypes
import numpy as np

from vxpy.core import camera_device
from vxpy.core import logger
from vxpy.core.camera_device import AbstractCameraDevice, CameraFormat
from vxpy.definitions import *
from vxpy.ext_lib.tis_windows import tisgrabber as tis

log = logger.getLogger(__name__)

ic = ctypes.cdll.LoadLibrary('tisgrabber_x64.dll')
tis.declareFunctions(ic)
ic.IC_InitLibrary(0)


class CallbackUserdata(ctypes.Structure):
    def __init__(self):
        ctypes.Structure.__init__(self)


class CameraDevice(camera_device.AbstractCameraDevice):

    manufacturer = 'TIS'

    _exposure_unit = camera_device.ExposureUnit.seconds

    # NOTE: TIS MAY only support 8-bit images for now?
    sink_formats = {'Y800': (1, np.uint8),  # (Y8) 8-bit monochrome
                    'RGB24': (3, np.uint8),  # 8-bit RGB
                    'RGB32': (4, np.uint8),  # 8-bit RGBA
                    # 'UYVY': (2, np.uint16),
                    'Y16': (1, np.uint16)}  # 16-bit monochrome

    def __init__(self, *args, **kwargs):
        camera_device.AbstractCameraDevice.__init__(self, *args, **kwargs)

        self._frame: np.ndarray = None

        # Open (empty) device
        self.h_grabber = ic.IC_CreateGrabber()

        # Set callback
        self.userdata = CallbackUserdata()
        self._frame_ready_callback = ic.FRAMEREADYCALLBACK(self._fetch_and_convert_buffer)
        ic.IC_SetFrameReadyCallback(self.h_grabber, self._frame_ready_callback, self.userdata)

    def _fetch_and_convert_buffer(self, h_grabber, p_buffer, frame_number, p_data):
        width = ctypes.c_long()
        height = ctypes.c_long()
        bits_per_pixel = ctypes.c_int()
        color_format = ctypes.c_int()

        # Query the image description values
        ic.IC_GetImageDescription(h_grabber, width, height, bits_per_pixel, color_format)

        # Calculate the buffer size
        bytes_per_pixel = int(bits_per_pixel.value / 8.0)
        buffer_size = width.value * height.value * bytes_per_pixel

        if buffer_size > 0:
            image = ctypes.cast(p_buffer, ctypes.POINTER(ctypes.c_ubyte * buffer_size))
            _dtype = self.sink_formats[self.format.dtype][1]
            _shape = (height.value, width.value, bytes_per_pixel // _dtype().nbytes)
            self._frame = np.ndarray(buffer=image.contents,
                                     dtype=_dtype,
                                     shape=_shape)

    def _get_property_value_range(self, property_name):
        value_min = ctypes.c_float()
        value_max = ctypes.c_float()
        ic.IC_GetPropertyAbsoluteValueRange(self.h_grabber, tis.T(property_name), tis.T('Value'), value_min, value_max)

        return value_min.value, value_max.value

    def _set_property(self, property_name, value):
        limits = self._get_property_value_range(property_name)
        if not limits[0] <= value <= limits[1]:
            log.warning(f'Cannot set value of property {property_name} to {value} '
                        f'on camera device {self}. Out of range {limits}')
            return

        # Set
        log.debug(f'Set property value of property {property_name} to {value} on device {self}')
        ic.IC_SetPropertyAbsoluteValue(self.h_grabber, tis.T(property_name), tis.T('Value'), ctypes.c_float(value))

        # Verify
        new_value = ctypes.c_float()
        ic.IC_GetPropertyAbsoluteValue(self.h_grabber, tis.T(property_name), tis.T('Value'), new_value)
        value_min, value_max = self._get_property_value_range(property_name)
        log.debug(f'New property value for {property_name} is {new_value.value:.5f} '
                  f'({value_min:.5f} - {value_max:.5f}) on device {self}')

    def _set_property_switch(self, property_name, switch_name, value):
        # Set
        ic.IC_SetPropertySwitch(self.h_grabber, tis.T(property_name), tis.T(switch_name), value)
        log.debug(f'Set property switch {switch_name} of property {property_name} to {value} on device {self}')

        # Verify
        new_value = ctypes.c_long()
        ic.IC_GetPropertySwitch(self.h_grabber, tis.T(property_name), tis.T(switch_name), new_value)
        log.debug(f'New property switch value {property_name}:{switch_name} '
                  f'is {new_value.value} on device {self}')

    def get_format_list(self) -> List[CameraFormat]:
        pass

    def _framerate_list(self, _format: CameraFormat) -> Tuple[float, float]:
        pass

    @classmethod
    def get_camera_list(cls) -> List[AbstractCameraDevice]:
        pass

    def _start_stream(self) -> bool:
        # Open device by model and serial
        ic.IC_OpenDevByUniqueName(self.h_grabber, tis.T(f'{self.model} {self.serial}'))

        # Setting
        format_str = f'{self.format.dtype} ({self.format.width}x{self.format.height})'
        ic.IC_SetVideoFormat(self.h_grabber, tis.T(format_str))
        ic.IC_SetFrameRate(self.h_grabber, ctypes.c_float(self.framerate))

        # Set to continuous mode
        ic.IC_SetContinuousMode(self.h_grabber, 0)

        # Set trigger enable
        ic.IC_SetPropertySwitch(self.h_grabber, tis.T("Trigger"), tis.T("Enable"), 1)

        # Set properties
        self._set_property_switch('Gain', 'Auto', 0)
        self._set_property_switch('Exposure', 'Auto', 0)
        self._set_property('Exposure', self.exposure)
        self._set_property('Gain', self.gain)

        # Start
        ic.IC_StartLive(self.h_grabber, 0)

        return True

    def snap_image(self) -> None:
        ic.IC_PropertyOnePush(self.h_grabber, tis.T("Trigger"), tis.T("Software Trigger"))

    def get_image(self) -> np.ndarray:
        return self._frame

    def end_stream(self) -> bool:
        ic.IC_StopLive(self.h_grabber)
        return True


if __name__ == '__main__':
    pass