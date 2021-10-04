"""
MappApp ./modules/__init__.py - General purpose digital/analog input/output modules.
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
import importlib
import time

from mappapp.api.attribute import read_attribute
from mappapp import Config
from mappapp import Def
from mappapp import Logging
from mappapp import protocols
from mappapp.core import process, ipc


class Io(process.AbstractProcess):
    name = Def.Process.Io

    _pid_pin_map = dict()
    _pid_attr_map = dict()
    _devices = dict()

    def __init__(self, **kwargs):
        process.AbstractProcess.__init__(self, **kwargs)

        for did, dev_config in Config.Io[Def.IoCfg.device].items():
            if not(all(k in dev_config for k in ("type", "model"))):
                Logging.write(Logging.WARNING, f'Insufficient information to configure device {did}')
                continue

            try:
                Logging.write(Logging.INFO, f'Set up device {did}')
                device_type_module = importlib.import_module(f'mappapp.devices.{dev_config["type"]}')
                device_cls = getattr(device_type_module, dev_config["model"])

                self._devices[did] = device_cls(dev_config)

            except Exception as exc:
                Logging.write(Logging.WARNING, f'Failed to set up device {did} // Exc: {exc}')
                continue

            if did in Config.Io[Def.IoCfg.pins]:
                Logging.write(Logging.INFO, f'Set up pin configuration for device {did}')

                pin_config = Config.Io[Def.IoCfg.pins][did]
                self._devices[did].configure_pins(**pin_config)

                # Map pins to flat dictionary
                for pid, pin in self._devices[did].pins.items():
                    self._pid_pin_map[pid] = pin
            else:
                Logging.write(Logging.WARNING, f'No pin configuration found for device {did}')

        # Set timeout during idle
        self.enable_idle_timeout = True

        self.timetrack = []
        # Run event loop
        self.run(interval=1./Config.Io[Def.IoCfg.max_sr])

    def start_protocol(self):
        self.protocol = protocols.load(ipc.Control.Protocol[Def.ProtocolCtrl.name])(self)

    def start_phase(self):
        self.set_record_group(f'phase_{ipc.Control.Protocol[Def.ProtocolCtrl.phase_id]}')

    def end_protocol(self):
        pass

    def set_outpin_to_attr(self, pid, attr_name):
        """Connect an output pin ID to a shared attribute. Attribute will be used as data to be written to pin."""

        if pid not in self._pid_pin_map:
            Logging.write(Logging.WARNING, f'Output "{pid}" has not been configured.')
            return

        pin = self._pid_pin_map[pid]

        if pin.config['type'] not in ('do', 'ao'):
            Logging.write(Logging.WARNING, f'{pin.config["type"].upper()}/{pid} has not been configured.')
            return

        if pid not in self._pid_attr_map:

            Logging.write(Logging.INFO, f'Set {pin.config["type"].upper()}/{pid} to attribute "{attr_name}"')
            self._pid_attr_map[pid] = attr_name
        else:
            Logging.write(Logging.WARNING, f'{pin.config["type"].upper()}/{pid} is already set.')

    def main(self):

        tt = []

        # Read data on pins once
        t = time.perf_counter()
        for pin in self._pid_pin_map.values():
            pin._read_data()
        tt.append(time.perf_counter()-t)

        # Write outputs from connected shared attributes
        t = time.perf_counter()
        for pid, attr_name in self._pid_attr_map.items():
            _, _, vals = read_attribute(attr_name)
            self._pid_pin_map[pid].write(vals[0][0])
        tt.append(time.perf_counter()-t)

        # Update routines with data
        # t = time.perf_counter()
        self.update_routines(**self._pid_pin_map)
        # tt.append(time.perf_counter()-t)

        self.timetrack.append(tt)
        if len(self.timetrack) >= 5000:
            # dts = np.array(self.timetrack)
            # means = dts.mean(axis=0) * 1000
            # stds = dts.std(axis=0) * 1000
            # print('Read data {:.2f} (+/- {:.2f}) ms'.format(means[0], stds[0]))
            # print('Write data {:.2f} (+/- {:.2f}) ms'.format(means[1], stds[1]))
            # print('Update routines {:.2f} (+/- {:.2f}) ms'.format(means[2], stds[2]))
            # print('----')
            self.timetrack = []

        if self._run_protocol():
            pass