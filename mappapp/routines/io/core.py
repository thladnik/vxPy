"""
MappApp ./routines/io/core.py
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
import time
import numpy as np

from mappapp import Config
from mappapp import Def
from mappapp.core.routine import ArrayAttribute, ArrayDType, IoRoutine
from mappapp.routines.camera.core import EyePositionDetection


class ReadAnalog(IoRoutine):

    def __init__(self, *args, **kwargs):
        IoRoutine.__init__(self, *args, **kwargs)

        self.pins = [tuple(s.split(':')) for s in Config.Io[Def.IoCfg.pins]]
        self.pins = [pin for pin in self.pins if pin[-1] == 'a'] # Select just inputs to read

        for pin_name, pin_num, pin_type in self.pins:
            setattr(self.buffer, pin_name, ArrayAttribute((1,), ArrayDType.float64))

    def execute(self, pin_data, device):
        for pin_name, pin_num, pin_type in self.pins:
            getattr(self.buffer, pin_name).write(pin_data[pin_name])


class ReadDigital(IoRoutine):

    def __init__(self, *args, **kwargs):
        IoRoutine.__init__(self, *args, **kwargs)

        self.pins = [tuple(s.split(':')) for s in Config.Io[Def.IoCfg.pins]]
        self.pins = [pin for pin in self.pins if pin[-1] == 'i'] # Select just inputs to read

        for pin_name, pin_num, pin_type in self.pins:
            setattr(self.buffer, pin_name, ArrayAttribute((1,), ArrayDType.float64))

    def execute(self, pin_data, device):
        for pin_name, pin_num, pin_type in self.pins:
            getattr(self.buffer, pin_name).write(pin_data[pin_name])


class TestTrigger(IoRoutine):

    def __init__(self, *args, **kwargs):
        IoRoutine.__init__(self, *args, **kwargs)

        self.exposed.append(TestTrigger.do_trigger)

        self.connect_to_trigger('saccade_trigger', EyePositionDetection, TestTrigger.do_trigger01)

    def execute(self, *args, **kwargs):
        pass

    def do_trigger01(self):
        print('I am so triggered!!! -.-"')

    def do_trigger(self,there):
        here = time.time()
        print('Time sent {:.5f} // Time received {:.5f} // Time diff {:.5f}'.format(there,here,here-there))

class TriggerLedArenaFlash(IoRoutine):

    def __init__(self, *args, **kwargs):
        IoRoutine.__init__(self, *args, **kwargs)

        # Make trigger function accessible
        self.exposed.append(TriggerLedArenaFlash.trigger_flash)
        self.exposed.append(TriggerLedArenaFlash.set_delay_ms)
        self.exposed.append(TriggerLedArenaFlash.set_delay_s)
        self.exposed.append(TriggerLedArenaFlash.set_duration_ms)
        self.exposed.append(TriggerLedArenaFlash.set_duration_s)

        # Connect to saccade trigger
        #self.connect_to_trigger('saccade_trigger', EyePositionDetection, TriggerLedArenaFlash.trigger_flash)

        self.pins = [tuple(s.split(':')) for s in Config.Io[Def.IoCfg.pins]]
        self.pins = [pin for pin in self.pins if pin[0].startswith('pwm_chan_out')]

        self.trigger_set = False
        self.flash_start_time = np.inf
        self.flash_end_time = -np.inf
        self.trigger_state = False

        # Set buffer attribute
        self.buffer.trigger_set = ArrayAttribute(shape=(1,), dtype=ArrayDType.uint8, length=20000)
        self.buffer.flash_state = ArrayAttribute(shape=(1,), dtype=ArrayDType.uint8, length=20000)

        self.delay = None
        self.duration = None

    def initialize(self):
        self.register_with_ui_plotter(TriggerLedArenaFlash, 'trigger_set', 1, name='Flash trigger', axis='di')
        self.register_with_ui_plotter(TriggerLedArenaFlash, 'flash_state', 1, name='Flash state', axis='di')

    def set_delay_ms(self, delay):
        self.set_delay_s(delay/1000)

    def set_delay_s(self,delay):
        self.delay = delay

    def set_duration_ms(self, duration):
        self.set_duration_s(duration/1000)

    def set_duration_s(self, duration):
        self.duration = duration

    def execute(self, pin_data, device):
        # Check saccade
        from mappapp import IPC
        from mappapp.routines.camera.core import EyePositionDetection
        _, _, le_sacc_val = IPC.Camera.read(EyePositionDetection, 'le_saccade_0')
        _, sacc_time, re_sacc_val = IPC.Camera.read(EyePositionDetection, 're_saccade_0')

        if re_sacc_val[0] > 0 or le_sacc_val[0] > 0:
            self.trigger_flash()

        t = time.time()
        state = self.flash_start_time <= t and self.flash_end_time > t

        for pin_id, pin_num, pin_type in self.pins:
            device.write(**{pin_id: int(state)})

        # Flash is over
        if self.trigger_state and t >= self.flash_end_time:
            self.trigger_state = False
            self.flash_start_time = np.inf
            self.flash_end_time = -np.inf

        self.buffer.trigger_set.write(self.trigger_set)
        self.buffer.flash_state.write(state)

        # Reset trigger set flag
        if self.trigger_set:
            self.trigger_set = not(self.trigger_set)

    def trigger_flash(self):
        # Can't trigger flash while script is reacting to last event
        if self.trigger_state:
            return

        print('Set flash start/end')
        self.trigger_set = not(self.trigger_set)
        self.trigger_state = not(self.trigger_state)
        self.flash_start_time = time.time() + self.delay
        self.flash_end_time = self.flash_start_time + self.duration