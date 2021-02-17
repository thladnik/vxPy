"""
MappApp ./visuals/ContiguousMotionNoise.py - icoCMN visuals
Copyright (C) 2020 Yue Zhang

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

import numpy as np
from scipy import signal
from vispy import gloo
from vispy.gloo import gl

from mappapp.utils import geometry
from mappapp.core.visual import SphericalVisual
from mappapp.utils.sphere import CMNIcoSphere


class IcoCMN(SphericalVisual):

    def __init__(self, *args):
        SphericalVisual.__init__(self, *args)

        # Set up model
        self.sphere = CMNIcoSphere(subdivisionTimes=2)
        self.index_buffer = gloo.IndexBuffer(self.sphere.indices)

        # Set up program and bind buffer
        self.cmn = gloo.Program(self.load_vertex_shader('spherical/v_tex.glsl'),
                                self.load_shader('f_tex.glsl'))

        Isize = self.index_buffer.size
        sp_sigma = 1  # spatial CR
        tp_sigma = 20  # temporal CR
        spkernel = np.exp(-(self.sphere.intertile_distance ** 2) / (2 * sp_sigma ** 2))
        spkernel *= spkernel > .001
        tp_min_length = np.int(np.ceil(np.sqrt(-2 * tp_sigma ** 2 * np.log(.01 * tp_sigma * np.sqrt(2 * np.pi)))))
        tpkernel = np.linspace(-tp_min_length, tp_min_length, num=2 * tp_min_length + 1)
        tpkernel = 1 / (tp_sigma * np.sqrt(2 * np.pi)) * np.exp(-tpkernel ** 2 / (2 * tp_sigma ** 2))
        tpkernel *= tpkernel > .0001

        flowvec = np.random.normal(size=[np.int(Isize / 3), 500, 3])  # Random white noise motion vector
        flowvec /= geometry.vecNorm(flowvec)[:,:,None]
        tpsmooth_x = signal.convolve(flowvec[:, :, 0], tpkernel[np.newaxis, :], mode='same')
        tpsmooth_y = signal.convolve(flowvec[:, :, 1], tpkernel[np.newaxis, :], mode='same')
        tpsmooth_z = signal.convolve(flowvec[:, :, 2], tpkernel[np.newaxis, :], mode='same')
        spsmooth_x = np.dot(spkernel, tpsmooth_x)
        spsmooth_y = np.dot(spkernel, tpsmooth_y)
        spsmooth_z = np.dot(spkernel, tpsmooth_z)  #
        spsmooth_Q = geometry.qn(np.array([spsmooth_x,spsmooth_y,spsmooth_z]).transpose([1,2,0]))

        tileCen_Q = geometry.qn(self.sphere.tile_center)
        tileOri_Q1 = geometry.qn(np.real(self.sphere.tile_orientation)).normalize[:,None]
        tileOri_Q2 = geometry.qn(np.imag(self.sphere.tile_orientation)).normalize[:,None]
        projected_motmat = geometry.projection(tileCen_Q[:,None],spsmooth_Q)
        self.motmatFull = geometry.qdot(tileOri_Q1,projected_motmat) - 1.j * geometry.qdot(tileOri_Q2,
                                                                                           projected_motmat)
        startpoint = geometry.cen2tri(np.random.rand(np.int(Isize / 3)),np.random.rand(np.int(Isize / 3)),.1)

        self.cmn['a_texcoord'] = startpoint.reshape([-1, 2]) / 2
        self.cmn['u_texture'] = np.uint8(np.random.randint(0, 2, [100, 100, 1]) * np.array([[[1, 1, 1]]]) * 255)
        self.cmn['u_texture'].wrapping = gl.GL_REPEAT

        self.i = 0

    def render(self, frame_time):
        # Update texture coordinates
        tidx = np.mod(self.i, 499)
        motmat = np.repeat(self.motmatFull[:, tidx], 3, axis=0)
        self.sphere.vertexBuffer['a_texcoord'] += np.array([np.real(motmat), np.imag(motmat)]).T / 1000

        # Call draw of main program
        self.apply_transform(self.cmn)
        self.cmn.draw('triangles', self.index_buffer)
        self.i += 1
