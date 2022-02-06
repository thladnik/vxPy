"""
vxpy ./visuals/spherical_uniform_background.py
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

from vxpy.core import visual
from vxpy.utils import sphere


class SphereUniformBackground(visual.SphericalVisual):
    u_color = 'u_color'

    def __init__(self, *args, **kwargs):
        visual.SphericalVisual.__init__(self, *args, **kwargs)

        self.sphere = sphere.UVSphere(azim_lvls=50, elev_lvls=25)
        self.index_buffer = gloo.IndexBuffer(self.sphere.indices)
        self.position_buffer = gloo.VertexBuffer(self.sphere.a_position)
        self.checker = gloo.Program(self.load_vertex_shader('./static_background.vert'),
                                    self.load_shader('./static_background.frag'))
        self.checker['a_position'] = self.position_buffer

    def initialize(self, *args, **kwargs):
        pass

    def render(self, frame_time):
        self.apply_transform(self.checker)
        self.checker.draw('triangles', self.index_buffer)
