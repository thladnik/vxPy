"""
MappApp ./gui/__init__.py
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
import os

import h5py
import numpy as np
from os.path import abspath
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QLabel
import pyqtgraph as pg

from vxpy import Config
from vxpy import Def
from vxpy.Def import *
from vxpy.core import ipc
from vxpy import Logging
from vxpy import modules
from vxpy.api.attribute import get_attribute, read_attribute
from vxpy.core.gui import IntegratedWidget, WindowWidget, WindowTabWidget


class ProcessMonitor(IntegratedWidget):

    def __init__(self, *args):
        IntegratedWidget.__init__(self,  'Process monitor', *args)

        self.exposed.append(ProcessMonitor.update_process_interval)

        self.state_labels = dict()
        self.state_widgets = dict()
        self.intval_widgets = dict()

        self._setup_ui()

    def _add_process(self, process_name):
        i = len(self.state_labels)
        self.state_labels[process_name] = QtWidgets.QLabel(process_name)
        self.state_labels[process_name].setStyleSheet('font-weight:bold;')
        self.layout().addWidget(self.state_labels[process_name], i * 2, 0)
        self.state_widgets[process_name] = QtWidgets.QLineEdit('')
        self.state_widgets[process_name].setDisabled(True)
        self.state_widgets[process_name].setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.layout().addWidget(self.state_widgets[process_name], i * 2, 1)
        self.intval_widgets[process_name] = QtWidgets.QLineEdit('')
        self.intval_widgets[process_name].setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.intval_widgets[process_name].setDisabled(True)
        self.layout().addWidget(self.intval_widgets[process_name], i * 2 + 1, 0, 1, 2)

    def _setup_ui(self):

        self.setFixedWidth(240)

        # Setup widget
        self.setLayout(QtWidgets.QGridLayout())
        # self.setMinimumSize(QtCore.QSize(0,0))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        # self.layout().setColumnMinimumWidth(2, 150)

        # Controller modules status
        self._add_process(Def.Process.Controller)
        # Camera modules status
        self._add_process(Def.Process.Camera)
        # Display modules status
        self._add_process(Def.Process.Display)
        # Gui modules status
        self._add_process(Def.Process.Gui)
        # IO modules status
        self._add_process(Def.Process.Io)
        # Worker modules status
        self._add_process(Def.Process.Worker)
        # Add spacer
        vSpacer = QtWidgets.QSpacerItem(1,1, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.layout().addItem(vSpacer, 6, 0)

        # Set timer for GUI update
        self._tmr_updateGUI = QtCore.QTimer()
        self._tmr_updateGUI.setInterval(100)
        self._tmr_updateGUI.timeout.connect(self._update_states)
        self._tmr_updateGUI.start()


    def update_process_interval(self, process_name, target_inval, mean_inval, std_inval):
        if process_name in self.intval_widgets:
            self.intval_widgets[process_name].setText('{:.1f}/{:.1f} ({:.1f}) ms'
                                                         .format(mean_inval * 1000,
                                                                 target_inval * 1000,
                                                                 std_inval * 1000))
        else:
            print(process_name, '{:.2f} +/- {:.2f}ms'.format(mean_inval * 1000, std_inval * 1000))

    def _set_process_state(self,le: QtWidgets.QLineEdit,code):
        # Set text
        le.setText(Def.MapStateToStr[code] if code in Def.MapStateToStr else '')

        # Set style
        if code == Def.State.IDLE:
            le.setStyleSheet('color: #3bb528; font-weight:bold;')
        elif code == Def.State.STARTING:
            le.setStyleSheet('color: #3c81f3; font-weight:bold;')
        elif code == Def.State.READY:
            le.setStyleSheet('color: #3c81f3; font-weight:bold;')
        elif code == Def.State.STOPPED:
            le.setStyleSheet('color: #d43434; font-weight:bold;')
        elif code == Def.State.RUNNING:
            le.setStyleSheet('color: #deb737; font-weight:bold;')
        else:
            le.setStyleSheet('color: #000000')

    def _update_states(self):
        for process_name, state_widget in self.state_widgets.items():
            self._set_process_state(state_widget, ipc.get_state(process_name))


class Recording(IntegratedWidget):

    def __init__(self, *args):
        IntegratedWidget.__init__(self, 'Recordings', *args)
        # Create inner widget
        self.setLayout(QtWidgets.QVBoxLayout())

        self.wdgt = QtWidgets.QWidget()
        self.wdgt.setLayout(QtWidgets.QGridLayout())
        self.wdgt.setObjectName('RecordingWidget')
        self.layout().addWidget(self.wdgt)

        vSpacer = QtWidgets.QSpacerItem(1,1, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)

        # Basic properties
        self.setCheckable(True)
        self.setMaximumWidth(400)

        # Current folder
        self.folder_wdgt = QtWidgets.QWidget()
        self.folder_wdgt.setLayout(QtWidgets.QGridLayout())
        self.folder_wdgt.layout().setContentsMargins(0, 0, 0, 0)

        self.folder_wdgt.layout().addWidget(QLabel('Base dir.'), 0, 0)
        self.base_dir = QtWidgets.QLineEdit('')
        self.base_dir.setDisabled(True)
        self.folder_wdgt.layout().addWidget(self.base_dir, 0, 1, 1, 2)

        self.select_folder = QtWidgets.QPushButton('Select...')
        self.select_folder.setDisabled(True)
        self.folder_wdgt.layout().addWidget(self.select_folder, 1, 1)
        self.open_folder = QtWidgets.QPushButton('Open')
        self.open_folder.clicked.connect(self.open_base_folder)
        self.folder_wdgt.layout().addWidget(self.open_folder, 1, 2)

        self.folder_wdgt.layout().addWidget(QLabel('Folder'), 2, 0)
        self.rec_folder = QtWidgets.QLineEdit()
        self.rec_folder.setEnabled(False)
        self.folder_wdgt.layout().addWidget(self.rec_folder, 2, 1, 1, 2)

        self.wdgt.layout().addWidget(self.folder_wdgt, 1, 0, 1, 2)
        self.hsep = QtWidgets.QFrame()
        self.hsep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.wdgt.layout().addWidget(self.hsep, 2, 0, 1, 2)

        # GroupBox
        self.clicked.connect(self.toggle_enable)

        # Left widget
        self.left_wdgt = QtWidgets.QWidget()
        self.left_wdgt.setLayout(QtWidgets.QVBoxLayout())
        self.left_wdgt.layout().setContentsMargins(0,0,0,0)
        self.wdgt.layout().addWidget(self.left_wdgt, 5, 0)

        # Data compression
        self.left_wdgt.layout().addWidget(QLabel('Compression'))
        self.compression_method = QtWidgets.QComboBox()
        self.compression_opts = QtWidgets.QComboBox()
        self.compression_method.addItems(['None', 'GZIP', 'LZF'])
        self.left_wdgt.layout().addWidget(self.compression_method)
        self.left_wdgt.layout().addWidget(self.compression_opts)
        self.compression_method.currentTextChanged.connect(self.set_compression_method)
        self.compression_method.currentTextChanged.connect(self.update_compression_opts)
        self.compression_opts.currentTextChanged.connect(self.set_compression_opts)

        # Buttons
        # Start
        self.btn_start = QtWidgets.QPushButton('Start')
        self.btn_start.clicked.connect(self.start_recording)
        self.left_wdgt.layout().addWidget(self.btn_start)
        # Pause
        self.btn_pause = QtWidgets.QPushButton('Pause')
        self.btn_pause.clicked.connect(self.pause_recording)
        self.left_wdgt.layout().addWidget(self.btn_pause)
        # Stop
        self.btn_stop = QtWidgets.QPushButton('Stop')
        self.btn_stop.clicked.connect(self.finalize_recording)
        self.left_wdgt.layout().addWidget(self.btn_stop)
        self.left_wdgt.layout().addItem(vSpacer)

        # Show recorded routines
        self.rec_routines = QtWidgets.QGroupBox('Recorded attributes')
        self.rec_routines.setLayout(QtWidgets.QVBoxLayout())
        self.rec_attribute_list = QtWidgets.QListWidget()

        self.rec_routines.layout().addWidget(self.rec_attribute_list)
        # Update recorded attributes
        for match_string in Config.Recording[Def.RecCfg.attributes]:
            self.rec_attribute_list.addItem(QtWidgets.QListWidgetItem(match_string))
        self.rec_routines.layout().addItem(vSpacer)
        self.wdgt.layout().addWidget(self.rec_routines, 5, 1)

        # Set timer for GUI update
        self.tmr_update_gui = QtCore.QTimer()
        self.tmr_update_gui.setInterval(200)
        self.tmr_update_gui.timeout.connect(self.update_ui)
        self.tmr_update_gui.start()

    def set_compression_method(self):
        ipc.rpc(Def.Process.Controller, modules.Controller.set_compression_method, self.get_compression_method())

    def set_compression_opts(self):
        ipc.rpc(Def.Process.Controller, modules.Controller.set_compression_opts, self.get_compression_opts())

    def open_base_folder(self):
        output_path = abspath(Config.Recording[Def.RecCfg.output_folder])
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(output_path.replace('\\', '/')))

    def start_recording(self):
        ipc.rpc(Def.Process.Controller, modules.Controller.start_manual_recording)

    def pause_recording(self):
        ipc.rpc(Def.Process.Controller, modules.Controller.pause_recording)

    def finalize_recording(self):
        # First: pause recording
        ipc.rpc(Def.Process.Controller, modules.Controller.pause_recording)

        reply = QtWidgets.QMessageBox.question(self, 'Finalize recording', 'Give me session data and stuff...',
                                               QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard,
                                               QtWidgets.QMessageBox.Save)
        if reply == QtWidgets.QMessageBox.Save:
            print('Save metadata and stuff...')
        else:
            reply = QtWidgets.QMessageBox.question(self, 'Confirm discard', 'Are you sure you want to DISCARD all recorded data?',
                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                                   QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                print('Fine... I`ll trash it all..')
            else:
                print('Puh... good choice')

        # Finally: stop recording
        print('Stop recording...')
        ipc.rpc(Def.Process.Controller, modules.Controller.stop_manual_recording)

    def toggle_enable(self, newstate):
        ipc.rpc(Def.Process.Controller, modules.Controller.set_enable_recording, newstate)

    def get_compression_method(self):
        method = self.compression_method.currentText()
        if method == 'None':
            method = None
        else:
            method = method.lower()

        return method

    def get_compression_opts(self):
        method = self.compression_method.currentText()
        opts = self.compression_opts.currentText()

        shuffle = opts.lower().find('shuffle') >= 0
        if len(opts) > 0 and method == 'GZIP':
            opts = dict(shuffle=shuffle,
                        compression_opts=int(opts[0]))
        elif method == 'LZF':
            opts = dict(shuffle=shuffle)
        else:
            opts = dict()

        return opts

    def update_compression_opts(self):
        self.compression_opts.clear()

        compr = self.compression_method.currentText()
        if compr == 'None':
            self.compression_opts.addItem('None')
        elif compr == 'GZIP':
            levels = range(10)
            self.compression_opts.addItems([f'{i} (shuffle)' for i in levels])
            self.compression_opts.addItems([str(i) for i in levels])
        elif compr == 'LZF':
            self.compression_opts.addItems(['None', 'Shuffle'])

    def update_ui(self):
        """(Periodically) update UI based on shared configuration"""

        enabled = ipc.Control.Recording[Def.RecCtrl.enabled]
        active = ipc.Control.Recording[Def.RecCtrl.active]
        current_folder = ipc.Control.Recording[Def.RecCtrl.folder]

        if active and enabled:
            self.wdgt.setStyleSheet('QWidget#RecordingWidget {background: rgba(179, 31, 18, 0.5);}')
        else:
            self.wdgt.setStyleSheet('QWidget#RecordingWidgetQGroupBox#RecGroupBox {background: rgba(0, 0, 0, 0.0);}')

        # Set enabled
        self.setCheckable(not(active) and not(bool(current_folder)))
        self.setChecked(enabled)

        # Set current folder
        self.rec_folder.setText(ipc.Control.Recording[Def.RecCtrl.folder])

        # Set buttons dis-/enabled
        # Start
        self.btn_start.setEnabled(not(active) and enabled)
        self.btn_start.setText('Start' if ipc.in_state(Def.State.IDLE, Def.Process.Controller) else 'Resume')
        # Pause // TODO: implement pause functionality during non-protocol recordings?
        #self._btn_pause.setEnabled(active and enabled)
        self.btn_pause.setEnabled(False)
        # Stop
        self.btn_stop.setEnabled(bool(ipc.Control.Recording[Def.RecCtrl.folder]) and enabled)
        # Overwrite stop button during protocol
        if bool(ipc.Control.Protocol[Def.ProtocolCtrl.name]):
            self.btn_stop.setEnabled(False)

        self.base_dir.setText(Config.Recording[Def.RecCfg.output_folder])


class Logger(IntegratedWidget):

    def __init__(self, *args):
        IntegratedWidget.__init__(self, 'Log', *args)

        self.setLayout(QtWidgets.QHBoxLayout())

        self.txe_log = QtWidgets.QTextEdit()
        self.txe_log.setReadOnly(True)
        self.txe_log.setFontFamily('Courier')
        self.layout().addWidget(self.txe_log)

        # Set initial log line count
        self.logccount = 0

        # Set timer for updating of log
        self.timer_logging = QtCore.QTimer()
        self.timer_logging.timeout.connect(self.print_log)
        self.timer_logging.start(50)

    def print_log(self):
        if ipc.Log.File is None:
            return

        if len(ipc.Log.History) > self.logccount:
            for rec in ipc.Log.History[self.logccount:]:

                self.logccount += 1

                # Skip for debug and unset
                if rec['levelno'] < 20:
                    continue

                # Info
                if rec['levelno'] == 20:
                    self.txe_log.setTextColor(QtGui.QColor('black'))
                    self.txe_log.setFontWeight(QtGui.QFont.Weight.Normal)
                # Warning
                elif rec['levelno'] == 30:
                    self.txe_log.setTextColor(QtGui.QColor('orange'))
                    self.txe_log.setFontWeight(QtGui.QFont.Weight.Bold)
                # Error and critical
                elif rec['levelno'] > 30:
                    self.txe_log.setTextColor(QtGui.QColor('red'))
                    self.txe_log.setFontWeight(QtGui.QFont.Weight.Bold)
                # Fallback
                else:
                    self.txe_log.setTextColor(QtGui.QColor('black'))
                    self.txe_log.setFontWeight(QtGui.QFont.Weight.Normal)

                # Add
                line = '{}  {:10}  {:10}  {}'.format(rec['asctime'], rec['name'], rec['levelname'], rec['msg'])
                self.txe_log.append(line)

import pprint


class Camera(WindowTabWidget):

    def __init__(self, *args):
        WindowTabWidget.__init__(self, 'Camera', *args)
        self.create_addon_tabs(Def.Process.Camera)

        # Select routine for FPS estimation (if any available)
        # If no routines are set, don't even start frame update timer
        self.stream_fps = 20
        if bool(Config.Camera[Def.CameraCfg.routines]):
            # Set frame update timer
            self.timer_frame_update = QtCore.QTimer()
            self.timer_frame_update.setInterval(1000 // self.stream_fps)
            self.timer_frame_update.timeout.connect(self.update_frames)
            self.timer_frame_update.start()

    def update_frames(self):
        # Update frames in tabbed widgets
        for idx in range(self.tab_widget.count()):
            self.tab_widget.widget(idx).update_frame()


class Display(WindowTabWidget):

    def __init__(self, *args):
        WindowTabWidget.__init__(self, 'Display', *args)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.create_addon_tabs(Def.Process.Display)


class Io(WindowTabWidget):

    def __init__(self, *args):
        WindowTabWidget.__init__(self, 'I/O', *args)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.create_addon_tabs(Def.Process.Io)


class Plotter(WindowWidget):

    # Colormap is tab10 from matplotlib:
    # https://matplotlib.org/3.1.0/tutorials/colors/colormaps.html
    cmap = \
        ((0.12156862745098039, 0.4666666666666667, 0.7058823529411765),
         (1.0, 0.4980392156862745, 0.054901960784313725),
         (0.17254901960784313, 0.6274509803921569, 0.17254901960784313),
         (0.8392156862745098, 0.15294117647058825, 0.1568627450980392),
         (0.5803921568627451, 0.403921568627451, 0.7411764705882353),
         (0.5490196078431373, 0.33725490196078434, 0.29411764705882354),
         (0.8901960784313725, 0.4666666666666667, 0.7607843137254902),
         (0.4980392156862745, 0.4980392156862745, 0.4980392156862745),
         (0.7372549019607844, 0.7411764705882353, 0.13333333333333333),
         (0.09019607843137255, 0.7450980392156863, 0.8117647058823529))

    mem_seg_len = 1000

    def __init__(self, *args):
        WindowWidget.__init__(self, 'Plotter', *args)

        hspacer = QtWidgets.QSpacerItem(1, 1,
                                        QtWidgets.QSizePolicy.Policy.Expanding,
                                        QtWidgets.QSizePolicy.Policy.Minimum)
        self.cmap = (np.array(self.cmap) * 255).astype(int)

        self.exposed.append(Plotter.add_buffer_attribute)

        self.setLayout(QtWidgets.QGridLayout())

        self.plot_widget = pg.PlotWidget()
        self.plot_item: pg.PlotItem = self.plot_widget.plotItem
        self.layout().addWidget(self.plot_widget, 1, 0, 1, 5)

        self.legend_item = pg.LegendItem()
        self.legend_item.setParentItem(self.plot_item)

        # Start timer
        self.tmr_update_data = QtCore.QTimer()
        self.tmr_update_data.setInterval(1000 // 20)
        self.tmr_update_data.timeout.connect(self.read_buffer_data)
        self.tmr_update_data.start()


        self.plot_data_items = dict()
        self.plot_num = 0
        self._interact = False
        self._xrange = 20
        self.plot_item.sigXRangeChanged.connect(self.set_new_xrange)
        self.plot_item.setXRange(-self._xrange, 0, padding=0.)
        self.plot_item.setLabels(left='defaulty')
        self.axes = {'defaulty': {'axis': self.plot_item.getAxis('left'),
                                  'vb': self.plot_item.getViewBox()}}
        self.plot_item.hideAxis('left')
        self.axis_idx = 3
        self.plot_data = dict()

        # Set auto scale checkbox
        self.check_auto_scale = QtWidgets.QCheckBox('Autoscale')
        self.check_auto_scale.stateChanged.connect(self.auto_scale_toggled)
        self.check_auto_scale.setChecked(True)
        self.layout().addWidget(self.check_auto_scale, 0, 0)
        self.auto_scale_toggled()
        # Scale inputs
        self.layout().addWidget(QLabel('X-Range'), 0, 1)
        # Xmin
        self.dsp_xmin = QtWidgets.QDoubleSpinBox()
        self.dsp_xmin.setRange(-10**6, 10**6)
        self.block_xmin = QtCore.QSignalBlocker(self.dsp_xmin)
        self.block_xmin.unblock()
        self.dsp_xmin.valueChanged.connect(self.ui_xrange_changed)
        self.layout().addWidget(self.dsp_xmin, 0, 2)
        # Xmax
        self.dsp_xmax = QtWidgets.QDoubleSpinBox()
        self.dsp_xmax.setRange(-10**6, 10**6)
        self.block_xmax = QtCore.QSignalBlocker(self.dsp_xmax)
        self.block_xmax.unblock()
        self.dsp_xmax.valueChanged.connect(self.ui_xrange_changed)
        self.layout().addWidget(self.dsp_xmax, 0, 3)
        self.layout().addItem(hspacer, 0, 4)
        # Connect viewbox range update signal
        self.plot_item.sigXRangeChanged.connect(self.update_ui_xrange)

        # Set up cache file
        temp_path = os.path.join(PATH_TEMP, '._plotter_temp.h5')
        if os.path.exists(temp_path):
            os.remove(temp_path)
        self.cache = h5py.File(temp_path, 'w')

    def ui_xrange_changed(self):
        self.plot_item.setXRange(self.dsp_xmin.value(), self.dsp_xmax.value(), padding=0.)

    def update_ui_xrange(self, *args):
        xrange = self.plot_item.getAxis('bottom').range
        self.block_xmin.reblock()
        self.dsp_xmin.setValue(xrange[0])
        self.block_xmin.unblock()

        self.block_xmax.reblock()
        self.dsp_xmax.setValue(xrange[1])
        self.block_xmax.unblock()

    def auto_scale_toggled(self, *args):
        self.auto_scale = self.check_auto_scale.isChecked()

    def mouseDoubleClickEvent(self, a0) -> None:
        # Check if double click on AxisItem
        click_pointf = QtCore.QPointF(a0.pos())
        items = [o for o in self.plot_item.scene().items(click_pointf) if isinstance(o, pg.AxisItem)]
        if len(items) == 0:
            return

        axis_item = items[0]

        # TODO: this flipping of pens doesn't work if new plotdataitems
        #   were added to the axis after the previous ones were hidden
        for id, data in self.plot_data.items():
            if axis_item.labelText == data['axis']:
                data_item: pg.PlotDataItem = self.plot_data_items[id]
                # Flip pen
                current_pen = data_item.opts['pen']
                if current_pen.style() == QtCore.Qt.PenStyle.NoPen:
                    data_item.setPen(data['pen'])
                else:
                    data_item.setPen(None)


        a0.accept()

    def set_new_xrange(self, vb, xrange):
        self._xrange = np.floor(xrange[1]-xrange[0])

    def update_views(self):
        for axis_name, ax in self.axes.items():
            ax['vb'].setGeometry(self.plot_item.vb.sceneBoundingRect())
            ax['vb'].linkedViewChanged(self.plot_item.vb, ax['vb'].XAxis)

    def add_buffer_attribute(self, attr_name, start_idx=0, name=None, axis=None):

        id = attr_name

        # Set axis
        if axis is None:
            axis = 'defaulty'

        # Set name
        if name is None:
            name = attr_name

        if axis not in self.axes:
            self.axes[axis] = dict(axis=pg.AxisItem('left'), vb=pg.ViewBox())

            self.plot_item.layout.addItem(self.axes[axis]['axis'], 2, self.axis_idx)
            self.plot_item.scene().addItem(self.axes[axis]['vb'])
            self.axes[axis]['axis'].linkToView(self.axes[axis]['vb'])
            self.axes[axis]['vb'].setXLink(self.plot_item)
            self.axes[axis]['axis'].setLabel(axis)

            self.update_views()
            self.plot_item.vb.sigResized.connect(self.update_views)
            self.axis_idx += 1

        if id not in self.plot_data:
            # Choose pen
            i = self.plot_num // len(self.cmap)
            m = self.plot_num % len(self.cmap)
            color = (*self.cmap[m], 255 // (2**i))
            pen = pg.mkPen(color)
            self.plot_num += 1

            # Set up cache group
            grp = self.cache.create_group(name)
            grp.create_dataset('x', shape=(0, ), chunks=(self.mem_seg_len, ), maxshape=(None, ), dtype=np.float32)
            grp.create_dataset('y', shape=(0, ), chunks=(self.mem_seg_len, ), maxshape=(None, ), dtype=np.float32)
            grp.create_dataset('mt', shape=(1, ), chunks=(self.mem_seg_len, ), maxshape=(None, ), dtype=np.float32)
            grp['mt'][0] = 0.

            # Set plot data
            self.plot_data[id] = {'axis': axis,
                                  'last_idx': None,
                                  'pen': pen,
                                  'name': name,
                                  'h5grp': grp}

        if id not in self.plot_data_items:

            # Create data item and add to axis viewbox
            data_item = pg.PlotDataItem([], [], pen=self.plot_data[id]['pen'])
            self.axes[axis]['vb'].addItem(data_item)

            # Add to legend
            self.legend_item.addItem(data_item, name)

            # Set data item
            self.plot_data_items[id] = data_item

    def read_buffer_data(self):

        for attr_name, data in self.plot_data.items():

            # Read new values from buffer
            try:
                last_idx = data['last_idx']

                # If no last_idx is set read last one and set to index if it is not None
                if last_idx is None:
                    n_idcs, n_times, n_data = read_attribute(attr_name)
                    if n_times[0] is None:
                        continue
                    data['last_idx'] = n_idcs[0]
                else:
                    # Read this attribute starting from the last_idx
                    n_idcs, n_times, n_data = read_attribute(attr_name, from_idx=last_idx)


            except Exception as exc:
                Logging.write(Logging.WARNING,
                              f'Problem trying to read attribute "{attr_name}" from_idx={data["last_idx"]}'
                              f'If this warning persists, DEFAULT_ARRAY_ATTRIBUTE_BUFFER_SIZE is possibly set too low.'
                              f'// Exception: {exc}')

                # In case of execution, assume that GUI is lagging behind temporarily and reset last_idx
                data['last_idx'] = None

                continue

            # No new datapoints to plot
            if len(n_times) == 0:
                continue

            try:
                n_times = np.array(n_times)
                n_data = np.array(n_data)
            except Exception as exc:
                continue

            # Set new last index
            data['last_idx'] = n_idcs[-1]

            try:
                # Reshape datasets
                old_n = data['h5grp']['x'].shape[0]
                new_n = n_times.shape[0]
                data['h5grp']['x'].resize((old_n + new_n, ))
                data['h5grp']['y'].resize((old_n + new_n, ))

                # Write new data
                data['h5grp']['x'][-new_n:] = n_times.flatten()
                data['h5grp']['y'][-new_n:] = n_data.flatten()

                # Set chunk time marker for indexing
                i_o = old_n // self.mem_seg_len
                i_n = (old_n + new_n) // self.mem_seg_len
                if i_n > i_o:
                    data['h5grp']['mt'].resize((i_n+1, ))
                    data['h5grp']['mt'][-1] = n_times[(old_n+new_n) % self.mem_seg_len]

            except Exception as exc:
                import traceback
                print(traceback.print_exc())

        self.update_plots()

    def update_plots(self):
        times = None
        for id, data_item in self.plot_data_items.items():

            grp = self.plot_data[id]['h5grp']

            if grp['x'].shape[0] == 0:
                continue

            if self.auto_scale:
                last_t = grp['x'][-1]
            else:
                last_t = self.plot_item.getAxis('bottom').range[1]

            first_t = last_t - self._xrange

            idcs = np.where(grp['mt'][:][grp['mt'][:] < first_t])
            if len(idcs[0]) > 0:
                start_idx = idcs[0][-1] * self.mem_seg_len
            else:
                start_idx = 0

            times = grp['x'][start_idx:]
            data = grp['y'][start_idx:]

            data_item.setData(x=times, y=data)

        # Update range
        if times is not None and self.auto_scale:
            self.plot_item.setXRange(times[-1] - self._xrange, times[-1], padding=0.)