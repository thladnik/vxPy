"""
MappApp ./visuals/Glider.py - Glider stimulus
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

from vispy import gloo
from vispy.gloo import gl
import numpy as np
import time

from Shader import BasicFileShader
from Visuals import SphericalVisual
from models import BasicSphere


class Glider2Point(SphericalVisual):

    def __init__(self, *args, p_parity):
        """
        :param protocol: protocol of which stimulus is currently part of

        """
        SphericalVisual.__init__(self, *args)

        ### Set up model
        self.sphere = BasicSphere.UVSphere(azim_lvls=60, elev_lvls=30)
        self.vertex_buffer = gloo.VertexBuffer(self.sphere.a_position)
        self.azimuth_buffer = gloo.VertexBuffer(self.sphere.a_azimuth)
        self.index_buffer = gloo.IndexBuffer(self.sphere.indices)

        ### Set up program
        self.glider = gloo.Program(
            BasicFileShader().addShaderFile('v_glider.glsl', subdir='spherical').read(),
            BasicFileShader().addShaderFile('f_glider.glsl', subdir='spherical').read())
        self.glider['a_position'] = self.vertex_buffer
        self.glider['a_azimuth'] = self.azimuth_buffer

        self.last_update = time.perf_counter()
        self.p_parity = p_parity  # -1 or 1

        self.seed_row = np.random.randint(0, 2, size=150, dtype=np.uint8)
        self.last_row = self.seed_row.copy()
        self.frame_seeds = []


    def render(self, frame_time):

        if time.perf_counter() >= self.last_update + 1/20:

            self.frame_seeds.append(np.random.randint(2))

            new_row = np.zeros(self.seed_row.shape[0], dtype=np.uint8)
            new_row[0] = self.frame_seeds[-1]

            for i in range(1, self.seed_row.shape[0]):

                ## Positive parity
                if self.p_parity < 0:
                    new_row[i] = not(self.last_row[i-1])
                else:
                    new_row[i] = self.last_row[i-1]

            self.last_update = time.perf_counter()

        else:
            new_row = self.last_row

        ### Render
        self.glider['u_texture'] = 255 * np.repeat(np.repeat(new_row[:,np.newaxis], 2, axis=-1).T[:,:,np.newaxis], 3, axis=-1)

        self.apply_transform(self.glider)
        self.glider.draw(gl.GL_TRIANGLES, self.index_buffer)

        ### Update last row
        self.last_row = new_row



class Glider3Point(SphericalVisual):

    def __init__(self, protocol, display, p_parity, p_mode):
        """
        :param protocol: protocol of which stimulus is currently part of

        """
        SphericalVisual.__init__(self, protocol, display)

        ### Set up model
        self.sphere = self.addModel('sphere',
                                    BasicSphere.UVSphere,
                                    theta_lvls=60, phi_lvls=30)
        self.sphere.createBuffers()

        ### Set up program
        self.glider = self.addProgram('glider',
                                      BasicFileShader().addShaderFile('v_glider.glsl', subdir='spherical').read(),
                                      BasicFileShader().addShaderFile('f_glider.glsl', subdir='spherical').read())
        self.glider.bind(self.sphere.vertexBuffer)

        self.last_update = time.perf_counter()
        self.p_parity = p_parity  # -1 or 1
        self.p_mode = p_mode  # 'conv' or 'div'

        self.seed_row = np.random.randint(0, 2, size=150, dtype=np.uint8)
        self.last_row = self.seed_row.copy()
        self.frame_seeds = []

        ### Debug
        self.lines = []


    def render(self):

        if time.perf_counter() >= self.last_update + 1/20:

            self.frame_seeds.append(np.random.randint(2))

            new_row = np.zeros(self.seed_row.shape[0], dtype=np.uint8)
            new_row[0] = self.frame_seeds[-1]

            for i in range(1, self.seed_row.shape[0]):
                v1 = self.last_row[i-1]

                ## Converging
                if self.p_mode == 'conv':
                    v2 = self.last_row[i]

                ## Diverging
                else:
                    v2 = new_row[i-1]

                ## Positive parity
                if self.p_parity == 1:
                    new_row[i] = v1 == v2

                ## Negative parity
                else:
                    new_row[i] = not(v1 == v2)

            self.last_update = time.perf_counter()

            self.lines.append(new_row)

        else:
            new_row = self.last_row

        ### Render
        self.glider['u_texture'] = 255 * np.repeat(np.repeat(new_row[:,np.newaxis], 2, axis=-1).T[:,:,np.newaxis], 3, axis=-1)
        self.glider.draw(gl.GL_TRIANGLES, self.sphere.indexBuffer)

        ### Update last row
        self.last_row = new_row


        if False and len(self.lines) > 400:
            import matplotlib.pyplot as plt
            plt.imshow(self.lines)
            plt.show()

            self.lines = []
