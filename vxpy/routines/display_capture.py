"""
vxPy ./routines/display/display_capture.py
Copyright (C) 2022 Tim Hladnik

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
from vxpy import calib

import vxpy.api.attribute as vxattribute
import vxpy.api.routine as vxroutine
import vxpy.core.visual as vxvisual


class Parameters(vxroutine.DisplayRoutine):
    """This routine buffers the visual parameters,
    but doesn't register them to be written to file continuously"""

    def setup(self):

        # Set up shared variables
        self.variable_parameters = vxattribute.ObjectAttribute('var_param')

    def initialize(self):
        self.variable_parameters.add_to_file()

    def main(self, visual: vxvisual.AbstractVisual):
        # Update variable parameters
        variable = {p.name: p.data for p in visual.variable_parameters}
        self.variable_parameters.write(variable)


class Frames(vxroutine.DisplayRoutine):

    def setup(self, *args, **kwargs):

        # Set up shared variables
        self.width = calib.CALIB_DISP_WIN_SIZE_WIDTH
        self.height = calib.CALIB_DISP_WIN_SIZE_HEIGHT
        self.frame = vxattribute.ArrayAttribute('display_frame',
                                                (self.height, self.width, 3),
                                                vxattribute.ArrayType.uint8)

    def initialize(self):
        self.frame.add_to_file()

    def main(self, visual: vxvisual.AbstractVisual):
        if visual is None:
            return

        frame = visual.frame.read('color', alpha=False)

        self.frame.write(frame)