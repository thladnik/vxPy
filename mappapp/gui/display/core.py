"""
MappApp ./gui/display/core.py
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
import inspect
import os
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QLabel
import time

from mappapp import Def
from mappapp import IPC
from mappapp import Logging
from mappapp import protocols
from mappapp import process
from mappapp.core.gui import AddonWidget
from mappapp.core.visual import BaseVisual, PlanarVisual, SphericalVisual
from mappapp.utils.gui import ComboBoxWidget, DoubleSliderWidget, IntSliderWidget


class Protocols(AddonWidget):

    def __init__(self, *args, **kwargs):
        AddonWidget.__init__(self, *args, **kwargs)
        self.setLayout(QtWidgets.QHBoxLayout())

        # Left
        self.left_widget = QtWidgets.QWidget()
        self.left_widget.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.left_widget)

        # File list
        self._lwdgt_files = QtWidgets.QListWidget()
        self._lwdgt_files.itemSelectionChanged.connect(self.update_file_list)
        self.left_widget.layout().addWidget(QLabel('Files'))
        self.left_widget.layout().addWidget(self._lwdgt_files)
        # Protocol list
        self.lwdgt_protocols = QtWidgets.QListWidget()
        self.left_widget.layout().addWidget(QLabel('Protocols'))
        self.left_widget.layout().addWidget(self.lwdgt_protocols)

        # Right
        self.right_widget = QtWidgets.QWidget()
        self.right_widget.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.right_widget)

        # Protocol (phase) progress
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setTextVisible(False)
        self.right_widget.layout().addWidget(self.progress)

        # Start button
        self.setLayout(QtWidgets.QVBoxLayout())
        self.btn_start = QtWidgets.QPushButton('Start protocol')
        self.btn_start.clicked.connect(self.start_protocol)
        self.right_widget.layout().addWidget(self.btn_start)
        # Abort protocol button
        self.btn_abort = QtWidgets.QPushButton('Abort protocol')
        self.btn_abort.clicked.connect(self.abort_protocol)
        self.right_widget.layout().addWidget(self.btn_abort)

        # Spacer
        vSpacer = QtWidgets.QSpacerItem(1,1, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.right_widget.layout().addItem(vSpacer)

        # Set update timer
        self._tmr_update = QtCore.QTimer()
        self._tmr_update.setInterval(50)
        self._tmr_update.timeout.connect(self.update_ui)
        self._tmr_update.start()

        # Once set up: compile file list for first time
        self._compile_file_list()

    def _compile_file_list(self):
        self._lwdgt_files.clear()
        self.btn_start.setEnabled(False)

        for file in protocols.all():
            self._lwdgt_files.addItem(file)

    def update_file_list(self):
        self.lwdgt_protocols.clear()
        self.btn_start.setEnabled(False)

        for protocol in protocols.read(protocols.open_(self._lwdgt_files.currentItem().text())):
            self.lwdgt_protocols.addItem(protocol.__name__)

    def update_ui(self):

        # Enable/Disable control elements
        ctrl_is_idle = IPC.in_state(Def.State.IDLE, Def.Process.Controller)
        self.btn_start.setEnabled(ctrl_is_idle and len(self.lwdgt_protocols.selectedItems()) > 0)
        self.lwdgt_protocols.setEnabled(ctrl_is_idle)
        self._lwdgt_files.setEnabled(ctrl_is_idle)
        protocol_is_running = bool(IPC.Control.Protocol[Def.ProtocolCtrl.name])
        self.btn_abort.setEnabled(protocol_is_running)

        # Update progress
        start_phase = IPC.Control.Protocol[Def.ProtocolCtrl.phase_start]
        if start_phase is not None:
            self.progress.setEnabled(True)
            phase_diff = time.time() - start_phase
            self.progress.setMaximum(int((IPC.Control.Protocol[Def.ProtocolCtrl.phase_stop] - start_phase) * 1000))
            if phase_diff > 0.:
                self.progress.setValue(int(phase_diff * 1000))

        if not(bool(IPC.Control.Protocol[Def.ProtocolCtrl.name])):
            self.progress.setEnabled(False)

    def start_protocol(self):
        file_name = self._lwdgt_files.currentItem().text()
        protocol_name = self.lwdgt_protocols.currentItem().text()

        # Start recording
        self.main.recordings.start_recording()

        # Start protocol
        IPC.rpc(Def.Process.Controller, process.Controller.start_protocol, '.'.join([file_name, protocol_name]))

    def abort_protocol(self):
        self.progress.setValue(0)
        self.progress.setEnabled(False)
        IPC.rpc(Def.Process.Controller, process.Controller.abortProtocol)


class VisualInteractor(AddonWidget):

    def __init__(self, *args, **kwargs):
        AddonWidget.__init__(self, *args, **kwargs)
        self.setLayout(QtWidgets.QHBoxLayout())

        self.left_widget = QtWidgets.QWidget(self)
        self.left_widget.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.left_widget)

        self.right_widget = QtWidgets.QWidget(self)
        self.right_widget.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.right_widget)

        # Set stretch
        self.layout().setStretchFactor(self.left_widget, 1)
        self.layout().setStretchFactor(self.right_widget, 1)

        # Tree widget
        self.tree = QtWidgets.QTreeWidget(self.left_widget)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(['', 'Description'])
        self.tree.itemCollapsed.connect(self.resize_columns)
        self.tree.itemExpanded.connect(self.resize_columns)
        self.left_widget.layout().addWidget(self.tree)
        self.tree.itemDoubleClicked.connect(self.start_visual)

        self.folders = dict()
        self.files = dict()
        self.visuals = dict()
        # TODO: add recursion for more directory levels?
        for folder in os.listdir(os.path.join(Def.package, Def.Path.Visual)):
            folder = str(folder)
            base_path = os.path.join(Def.package, Def.Path.Visual, folder)
            if os.path.isfile(base_path) or folder.startswith('_'):
                continue

            self.folders[folder] = QtWidgets.QTreeWidgetItem(self.tree)
            self.folders[folder].setText(0, folder)
            self.files[folder] = dict()
            self.visuals[folder] = dict()

            for file in os.listdir(base_path):
                file = str(file)
                full_path = os.path.join(base_path, file)
                if os.path.isdir(full_path) or file.startswith('_'):
                    continue

                self.files[folder][file] = QtWidgets.QTreeWidgetItem(self.folders[folder])
                self.files[folder][file].setText(0, file)
                self.visuals[folder][file] = dict()

                # Import module
                module = importlib.import_module('.'.join([Def.package,Def.Path.Visual,folder, file.split('.')[0]]))

                for clsname, cls in inspect.getmembers(module, inspect.isclass):
                    if not(issubclass(cls, (BaseVisual, PlanarVisual, SphericalVisual))) or cls in (PlanarVisual, SphericalVisual):
                        continue

                    self.visuals[folder][file][clsname] = (cls, QtWidgets.QTreeWidgetItem(self.files[folder][file]))
                    self.visuals[folder][file][clsname][1].setText(0, clsname)
                    self.visuals[folder][file][clsname][1].setText(1, cls.description)
                    self.visuals[folder][file][clsname][1].setData(0, QtCore.Qt.ToolTipRole, cls.description)
                    self.visuals[folder][file][clsname][1].setData(1, QtCore.Qt.ToolTipRole, cls.description)
                    # Set visual class to UserRole
                    self.visuals[folder][file][clsname][1].setData(0, QtCore.Qt.UserRole, (cls.__module__, cls.__name__))
                    #cls.__module__, cls.__name__

        # Add items
        self.tree.addTopLevelItems([folder_item for folder_item in self.folders.values()])

        # Buttons
        # Start
        self.btn_start = QtWidgets.QPushButton('Start visual')
        self.btn_start.clicked.connect(self.start_visual)
        self.left_widget.layout().addWidget(self.btn_start)
        # Stop
        self.btn_stop = QtWidgets.QPushButton('Stop visual')
        self.btn_stop.clicked.connect(self.stop_visual)
        self.left_widget.layout().addWidget(self.btn_stop)

        # Visual tuning widget
        self.tuner = QtWidgets.QGroupBox('Visual parameters',self.right_widget)
        self.tuner.setLayout(QtWidgets.QVBoxLayout())
        self.right_widget.layout().addWidget(self.tuner)

    def resize_columns(self):
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)

    def start_visual(self, item=False, column=False):
        if not(item):
            item = self.tree.currentItem()

        visual = item.data(0, QtCore.Qt.UserRole)

        if visual is None:
            return

        # TODO: Reload does not seem to work yet
        visual_module, visual_name = visual
        module = importlib.reload(importlib.import_module(visual_module))
        visual_cls = getattr(module, visual_name)

        # Clear layout
        self.clear_layout(self.tuner.layout())

        # Add UI components for visual
        for name, *args in visual_cls.interface:
            if isinstance(args[0], str):
                wdgt = ComboBoxWidget(name, args)
                wdgt.setParent(self.tuner)
            elif isinstance(args[0], int):
                kwargs = dict()
                if len(args) > 3:
                    kwargs = args.pop(-1)
                vdef, vmin, vmax = args
                wdgt = IntSliderWidget(name, vmin, vmax, vdef, **kwargs)
                wdgt.setParent(self.tuner)
            elif isinstance(args[0], float):
                kwargs = dict()
                if len(args) > 3:
                    kwargs = args.pop(-1)
                vdef, vmin, vmax = args
                wdgt = DoubleSliderWidget(name, vmin, vmax, vdef, **kwargs)
                wdgt.setParent(self.tuner)
            else:
                wdgt = QLabel(f'<{name}> has unclear type {type(args[0])}', self.tuner)

            wdgt.connect_to_result(self.update_parameter(name))
            self.tuner.layout().addWidget(wdgt)

        spacer = QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.tuner.layout().addItem(spacer)

        # TODO: this causes ValueError if visual_cls.paramters.values() contains a numpy.ndarray
        # if None in visual_cls.parameters.values():
        #     Logging.write(Logging.WARNING, 'Starting visual with some unset parameters.')

        IPC.rpc(Def.Process.Display, process.Display.start_visual, visual_cls, **visual_cls.parameters)

    def update_parameter(self, name):
        def _update(value):
            IPC.rpc(Def.Process.Display,process.Display.update_visual, **{name: value})
        return _update

    def stop_visual(self):
        IPC.rpc(Def.Process.Display, process.Display.stop_visual)

    def clear_layout(self, layout: QtWidgets.QLayout):
        while layout.count():
            child = layout.itemAt(0)
            if isinstance(child, QtWidgets.QSpacerItem):
                layout.removeItem(child)
            elif child.widget() is not None:
                child.widget().setParent(None)
            elif child.layout() is not None:
                self.clear_layout(child.layout())