"""
MappApp ./modules/controller.py
Controller spawns all sub processes.
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
import ctypes
import multiprocessing as mp
import os
import time
from typing import List, Dict, Tuple

from mappapp import Config
from mappapp import Def
from mappapp import Logging
from mappapp import modules
from mappapp import protocols
from mappapp.api.dependency import register_camera_device, register_io_device, assert_device_requirements
from mappapp.core import process, ipc
from mappapp.core import routine
from mappapp.utils import misc
from mappapp.core.attribute import Attribute


class Controller(process.AbstractProcess):
    name = Def.Process.Controller

    configfile: str = None

    _processes: Dict[str, mp.Process] = dict()
    _registered_processes: List[Tuple[process.AbstractProcess, Dict]] = list()

    _protocolized: List[str] = [Def.Process.Camera, Def.Process.Display, Def.Process.Io, Def.Process.Worker]
    _active_protocols: List[str] = list()

    def __init__(self, config_file):
        ipc.set_process(self)

        # Set up manager
        ipc.Manager = mp.Manager()

        # Set up logging
        ipc.Log.Queue = mp.Queue()
        ipc.Log.History = ipc.Manager.list()
        ipc.Log.File = ipc.Manager.Value(ctypes.c_char_p, '')

        # Set file to log to
        if ipc.Log.File.value == '':
            ipc.Log.File.value = f'{time.strftime("%Y-%m-%d-%H-%M-%S")}.log'

        # Set up logger, formatter and handler
        self.logger = Logging.setup_log()

        # Set program configuration
        try:
            Logging.write(Logging.INFO, f'Using configuration from file {config_file}')
            configuration = misc.ConfigParser()
            configuration.read(config_file)
            for section in configuration.sections():
                setattr(Config, section.capitalize(), configuration.getParsedSection(section))
            config_loaded = True

        except Exception:
            config_loaded = False
            import traceback
            traceback.print_exc()

        assert config_loaded, f'Loading of configuration file {config_file} failed.'

        # TODO: check if recording routines contains any entries
        #  for inactive processes or inactive routines on active processes
        #  print warning or just shut down completely in-case?

        # Manually set up pipe for controller
        ipc.Pipes[self.name] = mp.Pipe()

        # Set up modules proxies (TODO: get rid of IPC.State)
        _proxies = {
            Def.Process.Controller: process.ProcessProxy(Def.Process.Controller),
            Def.Process.Camera: process.ProcessProxy(Def.Process.Camera),
            Def.Process.Display: process.ProcessProxy(Def.Process.Display),
            Def.Process.Gui: process.ProcessProxy(Def.Process.Gui),
            Def.Process.Io: process.ProcessProxy(Def.Process.Io),
        }

        # Set up STATES
        ipc.State.Controller = ipc.Manager.Value(ctypes.c_int8, Def.State.NA)
        ipc.State.Camera = ipc.Manager.Value(ctypes.c_int8, Def.State.NA)
        ipc.State.Display = ipc.Manager.Value(ctypes.c_int8, Def.State.NA)
        ipc.State.Gui = ipc.Manager.Value(ctypes.c_int8, Def.State.NA)
        ipc.State.Io = ipc.Manager.Value(ctypes.c_int8, Def.State.NA)
        ipc.State.Worker = ipc.Manager.Value(ctypes.c_int8, Def.State.NA)

        ################################
        # Set up CONTROLS

        # General
        ipc.Control.General = ipc.Manager.dict()
        # Set avg. minimum sleep period
        times = list()
        for i in range(100):
            t = time.perf_counter()
            time.sleep(10 ** -10)
            times.append(time.perf_counter() - t)
        ipc.Control.General.update({Def.GenCtrl.min_sleep_time: max(times)})
        Logging.write(Logging.INFO, 'Minimum sleep period is {0:.3f}ms'.format(1000 * max(times)))
        ipc.Control.General.update({Def.GenCtrl.process_null_time: time.time() + 100.})

        # Check time precision on system
        dt = list()
        t0 = time.time()
        while len(dt) < 100:
            t1 = time.time()
            if t1 > t0:
                dt.append(t1 - t0)
        avg_dt = sum(dt) / len(dt)
        msg = 'Timing precision on system {0:3f}ms'.format(1000 * avg_dt)
        if avg_dt > 0.001:
            msg_type = Logging.WARNING
        else:
            msg_type = Logging.INFO
        Logging.write(msg_type, msg)

        # Recording
        ipc.Control.Recording = ipc.Manager.dict()
        ipc.Control.Recording.update({
            Def.RecCtrl.enabled: True,
            Def.RecCtrl.active: False,
            Def.RecCtrl.folder: ''})

        # Protocol
        ipc.Control.Protocol = ipc.Manager.dict({Def.ProtocolCtrl.name: None,
                                                 Def.ProtocolCtrl.phase_id: None,
                                                 Def.ProtocolCtrl.phase_start: None,
                                                 Def.ProtocolCtrl.phase_stop: None})

        # Load routine modules
        _routines = dict()
        _routines_to_load = dict()
        if Config.Camera[Def.CameraCfg.use]:
            _routines_to_load[Def.Process.Camera] = Config.Camera[Def.CameraCfg.routines]
        if Config.Display[Def.DisplayCfg.use]:
            _routines_to_load[Def.Process.Display] = Config.Display[Def.DisplayCfg.routines]
        if Config.Io[Def.CameraCfg.use]:
            _routines_to_load[Def.Process.Io] = Config.Io[Def.IoCfg.routines]

        for process_name, routines in _routines_to_load.items():
            _routines[process_name] = dict()
            for routine_file, routine_list in routines.items():

                # Load module (routine file)
                importpath = f'{Def.Path.Routines}.{process_name.lower()}.{routine_file}'
                module = __import__(importpath, fromlist=routine_list)

                # Load routine classes from module
                for routine_name in routine_list:
                    Logging.write(Logging.DEBUG, f'Load {process_name} routine from {importpath}.{routine_name}')

                    routine_cls = getattr(module, routine_name)

                    # Instantiate routine class
                    _routines[process_name][routine_cls.__name__]: routine.Routine = routine_cls()

        # Set configured cameras
        for dev_name in Config.Camera[Def.CameraCfg.device_id]:
            register_camera_device(dev_name)

        # Set configured io devices
        for dev_name in Config.Io[Def.IoCfg.device]:
            register_io_device(dev_name)

        # Compare required vs registered devices
        assert_device_requirements()

        # Set up routines
        for rs in _routines.values():
            for r in rs.values():
                r.setup()

        # Initialize AbstractProcess
        process.AbstractProcess.__init__(self, _program_start_time=time.time(), _routines=_routines, proxies=_proxies)

        # Set up processes
        # Worker
        self._register_process(modules.Worker)
        # GUI
        if Config.Gui[Def.GuiCfg.use]:
            self._register_process(modules.Gui)
        # Camera
        if Config.Camera[Def.CameraCfg.use]:
            self._register_process(modules.Camera)
        # Display
        if Config.Display[Def.DisplayCfg.use]:
            self._register_process(modules.Display)
        # IO
        if Config.Io[Def.IoCfg.use]:
            self._register_process(modules.Io)

        # Select subset of registered processes which should implement
        # the _run_protocol method
        _active_process_list = [p[0].__name__ for p in self._registered_processes]
        self._active_protocols = list(set(_active_process_list) & set(self._protocolized))
        Logging.write(Logging.INFO, f'Protocolized processes: {self._active_protocols}')

        # Set up protocol
        self.current_protocol = None

        self._init_params = dict(
            _program_start_time=self.program_start_time,
            _pipes=ipc.Pipes,
            _configurations={k: v for k, v in Config.__dict__.items() if not (k.startswith('_'))},
            _states={k: v for k, v
                     in ipc.State.__dict__.items()
                     if not (k.startswith('_'))},
            _proxies=_proxies,
            _routines=self._routines,
            _controls={k: v for k, v
                       in ipc.Control.__dict__.items()
                       if not (k.startswith('_'))},
            _log={k: v for k, v
                  in ipc.Log.__dict__.items()
                  if not (k.startswith('_'))},
            _attrs=Attribute.all
        )

        # Initialize all pipes
        for target, kwargs in self._registered_processes:
            ipc.Pipes[target.name] = mp.Pipe()

        # Initialize all processes
        for target, kwargs in self._registered_processes:
            self.initialize_process(target, **kwargs)

        # Run event loop
        self.start()

    def _register_process(self, target, **kwargs):
        """Register new modules to be spawned.

        :param target: modules class
        :param kwargs: optional keyword arguments for initalization of modules class
        """
        self._registered_processes.append((target, kwargs))

    def initialize_process(self, target, **kwargs):

        process_name = target.name

        if process_name in self._processes:
            # Terminate modules
            Logging.write(Logging.INFO, 'Restart modules {}'.format(process_name))
            self._processes[process_name].terminate()

            # Set modules state
            # (this is the ONLY instance where a modules state may be set externally)
            getattr(ipc.State, process_name).value = Def.State.STOPPED

            # Delete references
            del self._processes[process_name]

        # Update keyword args
        kwargs.update(self._init_params)

        # Create subprocess
        self._processes[process_name] = mp.Process(target=target, name=process_name, kwargs=kwargs)

        # Start subprocess
        self._processes[process_name].start()

        # Set state to IDLE
        self.set_state(Def.State.IDLE)

    def start(self):

        # Run controller
        self.run(interval=0.001)

        # This is where everything happens

        # Shutdown procedure
        Logging.write(Logging.DEBUG, 'Wait for processes to terminate')
        while True:
            # Complete shutdown if all processes are deleted
            if not (bool(self._processes)):
                break

            # Check status of processes until last one is stopped
            for process_name in list(self._processes):
                if not (getattr(ipc.State, process_name).value == Def.State.STOPPED):
                    continue

                # Terminate and delete references
                self._processes[process_name].terminate()
                del self._processes[process_name]
                del ipc.Pipes[process_name]

        self._running = False
        self.set_state(Def.State.STOPPED)

    ################
    # Recording

    def set_enable_recording(self, newstate):
        ipc.Control.Recording[Def.RecCtrl.enabled] = newstate

    def start_recording(self, compression_method=None, compression_opts=None):
        if ipc.Control.Recording[Def.RecCtrl.active]:
            Logging.write(Logging.WARNING, 'Tried to start new recording while active')
            return False

        if not (ipc.Control.Recording[Def.RecCtrl.enabled]):
            Logging.write(Logging.WARNING, 'Recording not enabled. Session will not be saved to disk.')
            return True

        # Set current folder if none is given
        if not (bool(ipc.Control.Recording[Def.RecCtrl.folder])):
            output_folder = Config.Recording[Def.RecCfg.output_folder]
            ipc.Control.Recording[Def.RecCtrl.folder] = os.path.join(output_folder,
                                                                     f'rec_{time.strftime("%Y-%m-%d-%H-%M-%S")}')

        # Create output folder
        rec_folder = ipc.Control.Recording[Def.RecCtrl.folder]
        Logging.write(Logging.DEBUG, 'Set output folder {}'.format(rec_folder))
        if not (os.path.exists(rec_folder)):
            Logging.write(Logging.DEBUG, 'Create output folder {}'.format(rec_folder))
            os.mkdir(rec_folder)

        ipc.Control.Recording[Def.RecCtrl.use_compression] = compression_method is not None
        ipc.Control.Recording[Def.RecCtrl.compression_method] = compression_method
        ipc.Control.Recording[Def.RecCtrl.compression_opts] = compression_opts

        # Set state to recording
        Logging.write(Logging.INFO, 'Start recording')
        ipc.Control.Recording[Def.RecCtrl.active] = True

        return True

    def pause_recording(self):
        if not (ipc.Control.Recording[Def.RecCtrl.active]):
            Logging.write(Logging.WARNING, 'Tried to pause inactive recording.')
            return

        Logging.write(Logging.INFO, 'Pause recording')
        ipc.Control.Recording[Def.RecCtrl.active] = False

    def stop_recording(self, sessiondata=None):
        if ipc.Control.Recording[Def.RecCtrl.active]:
            ipc.Control.Recording[Def.RecCtrl.active] = False

        if not (Config.Gui[Def.GuiCfg.use]) and sessiondata is None:
            # TODO: prompt user for sessiondata?
            pass

        # Save metadata and externally provided sessiondata
        metadata = dict(hello1name='test', hello2val=123)
        # TODO: compose proper metadata, append sessiondata and save to file

        Logging.write(Logging.INFO, 'Stop recording')
        self.set_state(Def.State.IDLE)
        ipc.Control.Recording[Def.RecCtrl.folder] = ''

    def start_protocol(self, protocol_path):
        # TODO: also make this dynamic
        # If any relevant subprocesses are currently busy: abort
        if not (self.in_state(Def.State.IDLE, Def.Process.Display)):
            processes = list()
            if not (self.in_state(Def.State.IDLE, Def.Process.Display)):
                processes.append(Def.Process.Display)
            if not (self.in_state(Def.State.IDLE, Def.Process.Io)):
                processes.append(Def.Process.Io)

            Logging.write(Logging.WARNING,
                          'One or more processes currently busy. Can not start new protocol.'
                          '(Processes: {})'.format(','.join(processes)))
            return

        # Start recording if enabled; abort if recording can't be started
        if ipc.Control.Recording[Def.RecCtrl.enabled] \
                and not (ipc.Control.Recording[Def.RecCtrl.active]):
            if not (self.start_recording()):
                return

        # Set phase info
        ipc.Control.Protocol[Def.ProtocolCtrl.phase_id] = None
        ipc.Control.Protocol[Def.ProtocolCtrl.phase_start] = None
        ipc.Control.Protocol[Def.ProtocolCtrl.phase_stop] = None
        # Set protocol class path
        ipc.Control.Protocol[Def.ProtocolCtrl.name] = protocol_path

        # Go into PREPARE_PROTOCOL
        self.set_state(Def.State.PREPARE_PROTOCOL)

    def start_protocol_phase(self, _id=None):
        # If phase ID was provided: run thcontrolsis ID
        if not (_id is None):
            ipc.Control.Protocol[Def.ProtocolCtrl.phase_id] = _id
            return

        # Else: advance protocol counter
        if ipc.Control.Protocol[Def.ProtocolCtrl.phase_id] is None:
            ipc.Control.Protocol[Def.ProtocolCtrl.phase_id] = 0
        else:
            ipc.Control.Protocol[Def.ProtocolCtrl.phase_id] = ipc.Control.Protocol[Def.ProtocolCtrl.phase_id] + 1

    def abortProtocol(self):
        # TODO: handle stuff?
        ipc.Control.Protocol[Def.ProtocolCtrl.phase_stop] = time.time()
        self.set_state(Def.State.PROTOCOL_END)

    def main(self):

        ########
        # First: handle logging
        while not (ipc.Log.Queue.empty()):

            # Fetch next record
            record = ipc.Log.Queue.get()

            try:
                self.logger.handle(record)
                ipc.Log.History.append(dict(levelno=record.levelno,
                                            asctime=record.asctime,
                                            name=record.name,
                                            levelname=record.levelname,
                                            msg=record.msg))
            except Exception:
                import sys, traceback
                print('Exception in Logger:', file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

        ########
        # PREPARE_PROTOCOL
        if self.in_state(Def.State.PREPARE_PROTOCOL):

            self.protocol = protocols.load(ipc.Control.Protocol[Def.ProtocolCtrl.name])(self)

            # Wait for processes to WAIT_FOR_PHASE (if they are not stopped)
            check = [not (ipc.in_state(Def.State.WAIT_FOR_PHASE, process_name))
                     for process_name in self._active_protocols]
            if any(check):
                return

            # Set next phase
            self.start_protocol_phase()

            # Set PREPARE_PHASE
            self.set_state(Def.State.PREPARE_PHASE)

        ########
        # PREPARE_PHASE
        if self.in_state(Def.State.PREPARE_PHASE):

            # Wait for processes to be ready (have phase prepared)
            check = [not (ipc.in_state(Def.State.READY, process_name))
                     for process_name in self._active_protocols]
            if any(check):
                return

            # Start phase
            phase_id = ipc.Control.Protocol[Def.ProtocolCtrl.phase_id]
            duration = self.protocol.fetch_phase_duration(phase_id)

            fixed_delay = 0.1
            ipc.Control.Protocol[Def.ProtocolCtrl.phase_start] = time.time() + fixed_delay
            ipc.Control.Protocol[Def.ProtocolCtrl.phase_stop] = time.time() + duration + fixed_delay

            Logging.write(Logging.INFO,
                          'Run phase {}. Set start time to {}'
                          .format(ipc.Control.Protocol[Def.ProtocolCtrl.phase_id],
                                  ipc.Control.Protocol[Def.ProtocolCtrl.phase_start]))

            # Set to running
            self.set_state(Def.State.RUNNING)

        ########
        # RUNNING
        elif self.in_state(Def.State.RUNNING):

            # If stop time is reached, set PHASE_END
            if ipc.Control.Protocol[Def.ProtocolCtrl.phase_stop] < time.time():
                Logging.write(Logging.INFO,
                              'End phase {}.'
                              .format(ipc.Control.Protocol[Def.ProtocolCtrl.phase_id]))

                self.set_state(Def.State.PHASE_END)

                return

        ########
        # PHASE_END
        elif self.in_state(Def.State.PHASE_END):

            # If there are no further phases, end protocol
            phase_id = ipc.Control.Protocol[Def.ProtocolCtrl.phase_id]
            if (phase_id + 1) >= self.protocol.phase_count():
                self.set_state(Def.State.PROTOCOL_END)
                return

            # Else, continue with next phase
            self.start_protocol_phase()

            # Move to PREPARE_PHASE (again)
            self.set_state(Def.State.PREPARE_PHASE)

        ########
        # PROTOCOL_END
        elif self.in_state(Def.State.PROTOCOL_END):

            # When all processes are in IDLE again, stop recording and
            # move Controller to IDLE
            check = [ipc.in_state(Def.State.IDLE, process_name)
                     for process_name in self._active_protocols]
            if all(check):
                self.stop_recording()

                ipc.Control.Protocol[Def.ProtocolCtrl.name] = ''

                self.set_state(Def.State.IDLE)

        else:
            # If nothing's happning: sleep for a bit
            time.sleep(0.05)

    def _start_shutdown(self):
        Logging.write(Logging.DEBUG, 'Shutdown requested. Checking.')

        # Check if any processes are still busy
        shutdown_state = True
        for p, _ in self._registered_processes:
            shutdown_state &= self.in_state(Def.State.IDLE, p.name) or self.in_state(Def.State.NA, p.name)

        # Check if recording is running
        shutdown_state &= not (ipc.Control.Recording[Def.RecCtrl.active])

        if not (shutdown_state):
            Logging.write(Logging.DEBUG, 'Not ready for shutdown. Confirming.')
            ipc.rpc(modules.Gui.name, modules.Gui.prompt_shutdown_confirmation)
            return

        self._force_shutdown()

    def _force_shutdown(self):
        Logging.write(Logging.DEBUG, 'Shut down processes')
        self._shutdown = True
        for process_name in self._processes:
            ipc.send(process_name, Def.Signal.shutdown)