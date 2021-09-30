"""
MappApp ./visuals/spherical/grating.py
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
import numpy as np
from vispy import gloo
from vispy import scene

from mappapp.core import visual
from mappapp.utils import sphere


class BlackWhiteGrating(visual.SphericalVisual):

    u_waveform = 'u_waveform'
    u_direction = 'u_direction'
    u_ang_velocity = 'u_ang_velocity'
    u_spat_period = 'u_spat_period'

    parameters = {u_waveform: 'rectangular',
                  u_direction: 'horizontal',
                  u_ang_velocity: 5.,
                  u_spat_period: 40.}

    def __init__(self, *args):
        visual.SphericalVisual.__init__(self, *args)

        # Set up sphere
        self.sphere = sphere.UVSphere(azim_lvls=60,elev_lvls=30)
        self.index_buffer = gloo.IndexBuffer(self.sphere.indices)
        self.position_buffer = gloo.VertexBuffer(self.sphere.a_position)
        self.azimuth_buffer = gloo.VertexBuffer(self.sphere.a_azimuth)
        self.elevation_buffer = gloo.VertexBuffer(self.sphere.a_elevation)

        # Set up program
        vert = self.load_vertex_shader('spherical/grating.vert')
        frag = self.load_shader('spherical/grating.frag')
        self.grating = gloo.Program(vert, frag)
        self.grating['a_position'] = self.position_buffer
        self.grating['a_azimuth'] = self.azimuth_buffer
        self.grating['a_elevation'] = self.elevation_buffer

    def initialize(self, **params):
        self.grating['u_stime'] = 0.0

        self.update(**params)

    def render(self, dt):
        self.grating['u_stime'] += dt

        self.apply_transform(self.grating)
        self.grating.draw('triangles', self.index_buffer)

    def parse_u_waveform(self, waveform):
        return 1 if waveform == 'rectangular' else 2  # 'sinusoidal'

    def parse_u_direction(self, direction):
        return 1 if direction == 'vertical' else 2  # 'horizontal'
