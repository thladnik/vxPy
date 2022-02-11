"""
MappApp ./core/protocol.py
Copyright (C) 2020 Tim Hladnik

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.l

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""
from __future__ import annotations
import importlib
from abc import abstractmethod
from inspect import isclass
from typing import List, Union, Callable, Type

from vxpy.core.visual import AbstractVisual
from vxpy.definitions import *
from vxpy.core import logger

log = logger.getLogger(__name__)

_available_protocols: List[str] = []


def get_available_protocol_paths(reload=False) -> List[str]:
    global _available_protocols

    if len(_available_protocols) > 0 and not reload:
        return _available_protocols

    _available_protocols = []
    basepath = PATH_PROTOCOL
    filelist = os.listdir(basepath)
    for filename in filelist:

        # Load protocol module
        path = '.'.join([*basepath.split(os.sep), filename.replace('.py', '')])
        try:
            mod = importlib.import_module(path)
        except Exception as exc:
            log.warning(f'Unable to load protocol {path}')
            import traceback
            print(traceback.print_exc())
            continue

        # Load protocols in module
        for s in dir(mod):
            # Skip everything that's not a protocol class
            obj = getattr(mod, s)
            if not isinstance(obj, type) or not issubclass(obj, AbstractProtocol):
                continue
            # Skip all base classses
            if obj == StaticPhasicProtocol:
                continue

            fullpath = f'{path}.{s}'

            _available_protocols.append(fullpath)

    return _available_protocols


def get_protocol(path: str) -> Union[Type[StaticPhasicProtocol], None]:
    if path not in get_available_protocol_paths():
        log.warning(f'Cannot get protocol {path}')
        return None

    # Return protocol class object
    parts = path.split('.')
    mod = importlib.import_module('.'.join(parts[:-1]))
    return getattr(mod, parts[-1])


class Phase:

    def __init__(self, duration=None,
                 action=None, action_params=None,
                 visual=None, visual_params=None):
        self.duration: Union[float, int] = duration

        self.action_parameters: Dict = action_params
        self.action = action

        self.visual: Union[AbstractVisual, Type[AbstractVisual], None] = visual
        self.visual_parameters: Dict = visual_params

    def set_duration(self, duration: float):
        self.duration = duration

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, value):
        self._action = value

    @property
    def visual(self):
        return self._visual

    @visual.setter
    def visual(self, value):
        self._visual = value

    @property
    def action_parameters(self):
        return {} if self._action_parameters is None else self._action_parameters

    @action_parameters.setter
    def action_parameters(self, value):
        self._action_parameters = value

    @property
    def visual_parameters(self):
        return {} if self._visual_parameters is None else self._visual_parameters

    @visual_parameters.setter
    def visual_parameters(self, value):
        self._visual_parameters = value

    def set_visual(self, visual_cls: Callable, parameters: dict):
        self._visual = visual_cls
        self._visual_parameters = parameters

    def set_action(self, action_cls: Callable, **kwargs):
        self._action = action_cls
        self._action_parameters = kwargs

    def initialize_action(self):
        if self._action is None:
            return False

        kwargs = {} if self._action_parameters is None else self._action_parameters
        self.action = self._action(**kwargs)

        return True

    def initialize_visual(self, canvas, _protocol):
        if self._visual is None:
            return False

        args = (canvas, )
        kwargs = dict(_protocol=_protocol)
        if isclass(self._visual):
            self._visual = self._visual(*args, **kwargs)
        else:
            self._visual = self._visual.__class__(*args, **kwargs)

        params = self.visual_parameters
        self._visual.update(params)

        return True


class AbstractProtocol:

    def __init__(self):
        self._phases: List[Phase] = []

    def add_phase(self, phase: Phase) -> None:
        self._phases.append(phase)

    def get_phase(self, phase_id: int) -> Union[Phase, None]:
        pass

    @abstractmethod
    def initialize_actions(self):
        pass

    @abstractmethod
    def initialize_visuals(self, canvas):
        pass


class StaticPhasicProtocol(AbstractProtocol):
    """Static experimental protocol which does NOT support closed-loop designs.
    """

    def __init__(self):
        AbstractProtocol.__init__(self)

    def initialize_actions(self):
        for phase in self._phases:
            phase.initialize_action()

    def initialize_visuals(self, canvas):
        for phase in self._phases:
            continue
            phase.initialize_visual(canvas, self)

    @property
    def phase_count(self):
        return len(self._phases)

    @property
    def duration(self):
        return sum([phase.duration for phase in self._phases if phase is not None])

    def fetch_phase_duration(self, phase_id):
        return self._phases[phase_id].duration

    def get_phase(self, phase_id: int) -> Union[Phase, None]:
        if phase_id < self.phase_count:
            return self._phases[phase_id]
        return None

