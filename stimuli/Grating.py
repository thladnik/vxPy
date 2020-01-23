"""
MappApp ./stimuli/Grating.py - Grating stimuli
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

from glumpy import gl

from Shader import BasicFileShader
from Stimulus import SphericalStimulus
from models import BasicSphere

class BlackWhiteGrating(SphericalStimulus):

    def __init__(self, protocol, display, orientation, shape, velocity, num):
        """
        :param protocol: protocol of which stimulus is currently part of

        :param orientation: orientation of grating; either 'vertical' or 'horizontal'
        :param shape: shape of underlying func; either 'rectangular' or 'sinusoidal'
        :param velocity:
        :param num:
        """
        SphericalStimulus.__init__(self, protocol, display)

        self.model = self.addModel('sphere',
                                   BasicSphere.UVSphere,
                                   theta_lvls=60, phi_lvls=30)
        self.program = self.addProgram('program',
                                       BasicFileShader().addShaderFile('v_grating.glsl', subdir='spherical').read(),
                                       BasicFileShader().addShaderFile('f_grating.glsl', subdir='spherical').read())
        self.program.bind(self.model.vertexBuffer)

        self.update(shape=shape, orientation=orientation, velocity=velocity, num=num)

    def render(self):
        self.program.draw(gl.GL_TRIANGLES, self.model.indexBuffer)

    def update(self, shape=None, orientation=None, velocity=None, num=None):

        if shape is not None:
            self._setShape(shape)

        if orientation is not None:
            self._setOrientation(orientation)

        if velocity is not None:
            self.program['u_velocity'] = velocity

        if num is not None and num > 0:
            self.program['u_stripes_num'] = num

    def _setShape(self, shape):
        if shape == 'rectangular':
            self.program['u_shape'] = 1
        elif shape == 'sinusoidal':
            self.program['u_shape'] = 2

    def _setOrientation(self, orientation):
        if orientation == 'vertical':
            self.program['u_orientation'] = 1
        elif orientation == 'horizontal':
            self.program['u_orientation'] = 2