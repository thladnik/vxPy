"""
MappApp ./process/Core.py - General purpose digital/analog input/output process.
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

from mappapp.core.process import AbstractProcess
from mappapp import protocols,Logging,IPC,Def,Config


class Io(AbstractProcess):
    name = Def.Process.Io

    def __init__(self, **kwargs):
        AbstractProcess.__init__(self, **kwargs)

        ################################
        ### Set up device
        self.device = None
        if Config.Io[Def.IoCfg.device_type] == 'Arduino':
            import mappapp.devices.Arduino
            self.device = mappapp.devices.Arduino.Device()

        run = False
        try:
            if self.device is None:
                raise Exception('No applicable device found.')
            else:
                run = self.device.connect() and self.device.setup()

        except Exception as exc:
            Logging.write(Logging.WARNING,f'Could not connect to device. // Exception: {exc}')
            self.set_state(Def.State.STOPPED)


        # Disable timeout during idle
        self.enable_idle_timeout = False

        # Run event loop
        if run:
            self.run(interval=1. / Config.Io[Def.IoCfg.sample_rate])

    def _prepare_protocol(self):
        self.protocol = protocols.load(IPC.Control.Protocol[Def.ProtocolCtrl.name])(self)

    def _prepare_phase(self):
        pass

    def _cleanup_protocol(self):
        pass

    def main(self):

        # Update routines
        self.update_routines(self.device.read_all(), self.device)

        if self._run_protocol():
            pass

