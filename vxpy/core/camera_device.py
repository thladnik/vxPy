"""
vxPy ./core/camera_device.py
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
from __future__ import annotations
from abc import ABC, abstractmethod
import importlib
from enum import Enum
from typing import Any, Dict, Tuple, Type, Union, List
import numpy as np

from vxpy.core import logger

log = logger.getLogger(__name__)


def get_camera(device_config: Dict[str, Any]) -> Union[AbstractCameraDevice, None]:
    try:
        # Import api
        _module = importlib.import_module(device_config['api'])
        camera_class = getattr(_module, 'CameraDevice')

    except Exception as exc:
        log.error(f'Failed to load camera API {device_config["api"]} // {exc}')
        return

    else:
        #  Set up camera using configuration
        camera = camera_class(**device_config)

        return camera


class AbstractCameraDevice(ABC):
    manufacturer: str = None

    _exposure_unit: ExposureUnit = None

    sink_formats: Dict[str, Tuple[int, Type[np.dtype]]] = None

    # E.g. sink_formats = {'BGRA': (4, np.uint8),
    #                      'GRAY8': (1, np.uint8),
    #                      'GRAY16': (1, np.uint16)}

    def __init__(self, serial, model,
                 _format=None,
                 dtype=None,
                 width=None,
                 height=None,
                 framerate=None,
                 exposure=None,
                 gain=None,
                 **info):

        self.serial = serial
        self.model = model
        self.set_format(_format, dtype, width, height)
        self.framerate = framerate
        self.exposure = exposure
        self.gain = gain
        self.info = info

    def __repr__(self):
        return f'Camera {self.manufacturer}({self.model}, {self.serial}) @ {self.format}'

    @property
    def exposure(self) -> float:
        scale = 1
        if self._exposure_unit is not None:
            scale = 10 ** self._exposure_unit.value

        return self._exposure * scale

    @exposure.setter
    def exposure(self, value) -> None:
        self._exposure = value

    @property
    def gain(self) -> float:
        return self._gain

    @gain.setter
    def gain(self, value: float) -> None:
        self._gain = value

    @property
    def framerate(self) -> float:
        return self._framerate

    @framerate.setter
    def framerate(self, value: float) -> None:
        self._framerate = value

    def set_format(self,
                   fmt: Union[CameraFormat, None] = None,
                   dtype: Union[str, None] = None,
                   width: Union[int, None] = None,
                   height: Union[int, None] = None) -> None:

        if fmt is None and all([p is not None for p in [dtype, width, height]]):
            fmt = CameraFormat(dtype, width, height)

        self.format = fmt

    @abstractmethod
    def get_format_list(self) -> List[CameraFormat]:
        pass

    @abstractmethod
    def _framerate_list(self, _format: CameraFormat) -> List[float]:
        pass

    def get_framerate_list(self, _format: Union[CameraFormat, None] = None) -> List[float]:
        if _format is None:
            if self.format is None:
                raise AttributeError('Camera format is needed to determine framerate range')
            _format = self.format

        return self._framerate_list(_format)

    @classmethod
    @abstractmethod
    def get_camera_list(cls) -> List[AbstractCameraDevice]:
        pass

    @abstractmethod
    def _start_stream(self) -> bool:
        pass

    def start_stream(self) -> bool:
        if self.format is None:
            log.error(f'Tried starting camera stream of {self} without format set.')
            return False

        # Try connecting
        try:
            return self._start_stream()

        except Exception as exc:
            log.error(f'Failed to set up virtual camera {self}: {exc}')
            return False

    @abstractmethod
    def snap_image(self) -> bool:
        pass

    @abstractmethod
    def get_image(self) -> np.ndarray:
        pass

    @abstractmethod
    def end_stream(self) -> bool:
        pass


class ExposureUnit(Enum):
    seconds = -3
    milliseconds = 0
    microseconds = 3
    nanoseconds = 6


class CameraFormat:

    def __init__(self, dtype: Any, width: int, height: int):
        self.dtype = dtype
        self.width = width
        self.height = height

    def __repr__(self) -> str:
        return f'{self.dtype}({self.width}x{self.height})'

    def __eq__(self, other):
        if not isinstance(other, CameraFormat):
            raise NotImplemented
        return self.dtype == other.dtype \
               and self.height == other.height \
               and self.width == other.width

    @staticmethod
    def from_str(fmt_str: str) -> CameraFormat:
        substr = fmt_str[0].split('(')
        f = substr[0]
        w, h = [int(i) for i in substr[-1].strip(')').split('x')]

        return CameraFormat(f, w, h)


if __name__ == '__main__':
    pass