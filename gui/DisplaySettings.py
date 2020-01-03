from PyQt5 import QtCore, QtWidgets

import MappApp_Definition as madef
from helper import MappApp_Helper as mahelp


class DisplaySettings(QtWidgets.QWidget):

    def __init__(self, _main):
        self._main = _main
        QtWidgets.QWidget.__init__(self, parent=None, flags=QtCore.Qt.Window)


        self._main._registerCallback('_setConfiguration', self._setConfiguration)
        self._main._queryPropertyFromCtrl('_displayConfiguration', callback='_setConfiguration')

        self._setupUi()

    def _setupUi(self):
        self.setMinimumSize(400, 400)

        ## Setup widget
        self.setWindowTitle('Display settings')
        self.setLayout(QtWidgets.QVBoxLayout())

        ## Setup position
        self._grp_position = QtWidgets.QGroupBox('Position')
        self._grp_position.setLayout(QtWidgets.QGridLayout())
        self.layout().addWidget(self._grp_position)
        # X Position
        self._dspn_x_pos = QtWidgets.QDoubleSpinBox()
        self._dspn_x_pos.setDecimals(3)
        self._dspn_x_pos.setMinimum(-1.0)
        self._dspn_x_pos.setMaximum(1.0)
        self._dspn_x_pos.setSingleStep(.001)
        self._grp_position.layout().addWidget(QtWidgets.QLabel('X-position'), 0, 0)
        self._grp_position.layout().addWidget(self._dspn_x_pos, 0, 1)
        # Y position
        self._dspn_y_pos = QtWidgets.QDoubleSpinBox()
        self._dspn_y_pos.setDecimals(3)
        self._dspn_y_pos.setMinimum(-1.0)
        self._dspn_y_pos.setMaximum(1.0)
        self._dspn_y_pos.setSingleStep(.001)
        self._grp_position.layout().addWidget(QtWidgets.QLabel('Y-position'), 1, 0)
        self._grp_position.layout().addWidget(self._dspn_y_pos, 1, 1)
        # Distance from center
        self._dspn_vp_center_offset = QtWidgets.QDoubleSpinBox()
        self._dspn_vp_center_offset.setDecimals(3)
        self._dspn_vp_center_offset.setMinimum(-1.0)
        self._dspn_vp_center_offset.setMaximum(1.0)
        self._dspn_vp_center_offset.setSingleStep(.001)
        self._grp_position.layout().addWidget(QtWidgets.QLabel('Radial offset'), 2, 0)
        self._grp_position.layout().addWidget(self._dspn_vp_center_offset, 2, 1)

        ## Setup view
        self._grp_view = QtWidgets.QGroupBox('View')
        self._grp_view.setLayout(QtWidgets.QGridLayout())
        self.layout().addWidget(self._grp_view)
        # Elevation
        self._dspn_elev_angle = QtWidgets.QDoubleSpinBox()
        self._dspn_elev_angle.setDecimals(1)
        self._dspn_elev_angle.setMinimum(-90.0)
        self._dspn_elev_angle.setMaximum(90.0)
        self._dspn_elev_angle.setSingleStep(0.1)
        self._grp_view.layout().addWidget(QtWidgets.QLabel('Elevation [deg]'), 0, 0)
        self._grp_view.layout().addWidget(self._dspn_elev_angle, 0, 1)
        # Offset of view from axis towards origin of sphere
        self._dspn_view_axis_offset = QtWidgets.QDoubleSpinBox()
        self._dspn_view_axis_offset.setDecimals(3)
        self._dspn_view_axis_offset.setMinimum(-1.0)
        self._dspn_view_axis_offset.setMaximum(1.0)
        self._dspn_view_axis_offset.setSingleStep(.001)
        self._grp_view.layout().addWidget(QtWidgets.QLabel('Origin offset'), 1, 0)
        self._grp_view.layout().addWidget(self._dspn_view_axis_offset, 1, 1)
        # Distance from origin of sphere
        self._dspn_view_origin_distance = QtWidgets.QDoubleSpinBox()
        self._dspn_view_origin_distance.setDecimals(1)
        self._dspn_view_origin_distance.setMinimum(1.5)
        self._dspn_view_origin_distance.setMaximum(10.)
        self._dspn_view_origin_distance.setSingleStep(.1)
        self._grp_view.layout().addWidget(QtWidgets.QLabel('Origin distance'), 2, 0)
        self._grp_view.layout().addWidget(self._dspn_view_origin_distance, 2, 1)
        # Field of view
        self._dspn_fov = QtWidgets.QDoubleSpinBox()
        self._dspn_fov.setDecimals(1)
        self._dspn_fov.setMinimum(1.0)
        self._dspn_fov.setMaximum(180.0)
        self._dspn_fov.setSingleStep(0.5)
        self._grp_view.layout().addWidget(QtWidgets.QLabel('FOV'), 3, 0)
        self._grp_view.layout().addWidget(self._dspn_fov, 3, 1)

        ## Setup display
        self._grp_disp = QtWidgets.QGroupBox('Display')
        self._grp_disp.setLayout(QtWidgets.QGridLayout())
        self.layout().addWidget(self._grp_disp)
        # Screen ID
        self._spn_screen_id = QtWidgets.QSpinBox()
        self._grp_disp.layout().addWidget(QtWidgets.QLabel('Screen'), 0, 0)
        self._grp_disp.layout().addWidget(self._spn_screen_id, 0, 1)
        # Use fullscreen
        self._check_fullscreen = QtWidgets.QCheckBox('Fullscreen')
        self._check_fullscreen.setTristate(False)
        self._grp_disp.layout().addWidget(self._check_fullscreen, 0, 2)

        ## Connect change events to a timer
        # Define update timer
        self.timer_param_update = QtCore.QTimer()
        self.timer_param_update.setSingleShot(True)
        self.timer_param_update.timeout.connect(self.settingsChanged)
        # Timer delay
        td = 250
        # Connect to timer
        self._dspn_x_pos.valueChanged.connect(lambda: self.timer_param_update.start(td))
        self._dspn_y_pos.valueChanged.connect(lambda: self.timer_param_update.start(td))
        self._dspn_elev_angle.valueChanged.connect(lambda: self.timer_param_update.start(td))
        self._dspn_view_axis_offset.valueChanged.connect(lambda: self.timer_param_update.start(td))
        self._dspn_vp_center_offset.valueChanged.connect(lambda: self.timer_param_update.start(td))
        self._dspn_view_origin_distance.valueChanged.connect(lambda: self.timer_param_update.start(td))
        self._check_fullscreen.stateChanged.connect(lambda: self.timer_param_update.start(td))
        self._dspn_fov.valueChanged.connect(lambda: self.timer_param_update.start(td))

    def _setConfiguration(self, **_configuration):

        if madef.DisplayConfig.float_pos_glob_x_pos in _configuration:
            self._dspn_x_pos.setValue(_configuration[madef.DisplayConfig.float_pos_glob_x_pos])

        if madef.DisplayConfig.float_pos_glob_y_pos in _configuration:
            self._dspn_y_pos.setValue(_configuration[madef.DisplayConfig.float_pos_glob_y_pos])

        if madef.DisplayConfig.float_view_elev_angle in _configuration:
            self._dspn_elev_angle.setValue(_configuration[madef.DisplayConfig.float_view_elev_angle])

        if madef.DisplayConfig.float_view_axis_offset in _configuration:
            self._dspn_view_axis_offset.setValue(_configuration[madef.DisplayConfig.float_view_axis_offset])

        if madef.DisplayConfig.float_pos_glob_radial_offset in _configuration:
            self._dspn_vp_center_offset.setValue(_configuration[madef.DisplayConfig.float_pos_glob_radial_offset])

        if madef.DisplayConfig.float_view_origin_distance in _configuration:
            self._dspn_view_origin_distance.setValue(_configuration[madef.DisplayConfig.float_view_origin_distance])

        if madef.DisplayConfig.float_view_fov in _configuration:
            self._dspn_fov.setValue(_configuration[madef.DisplayConfig.float_view_fov])

        if madef.DisplayConfig.int_disp_screen_id in _configuration:
            self._spn_screen_id.setValue(_configuration[madef.DisplayConfig.int_disp_screen_id])

        if madef.DisplayConfig.float_pos_glob_x_pos in _configuration:
            self._check_fullscreen.setCheckState(
                mahelp.Conversion.boolToQtCheckstate(_configuration[madef.DisplayConfig.float_pos_glob_x_pos]))


    def settingsChanged(self):
        self._main._sendToCtrl([madef.Process.Signal.setProperty, '_displayConfiguration', {
            madef.DisplayConfig.float_pos_glob_x_pos           : self._dspn_x_pos.value(),
            madef.DisplayConfig.float_pos_glob_y_pos           : self._dspn_y_pos.value(),
            madef.DisplayConfig.float_view_elev_angle          : self._dspn_elev_angle.value(),
            madef.DisplayConfig.float_view_axis_offset         : self._dspn_view_axis_offset.value(),
            madef.DisplayConfig.float_pos_glob_radial_offset   : self._dspn_vp_center_offset.value(),
            madef.DisplayConfig.float_view_origin_distance     : self._dspn_view_origin_distance.value(),
            madef.DisplayConfig.float_view_fov                 : self._dspn_fov.value(),
            madef.DisplayConfig.int_disp_screen_id             : self._spn_screen_id.value(),
            madef.DisplayConfig.bool_disp_fullscreen           : mahelp.Conversion.QtCheckstateToBool(
                self._check_fullscreen.checkState())
        }])



