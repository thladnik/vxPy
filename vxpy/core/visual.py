"""
MappApp ./core/visual.py
Copyright (C) 2020 Tim Hladnik, Yue Zhang

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
from abc import ABC, abstractmethod
import numpy as np
import os
from typing import Any, Dict
from vispy import app
from vispy import gloo
from vispy.gloo import gl
from vispy.util import transforms

from vxpy import Config
from vxpy import Def
from vxpy import Logging
from vxpy.utils import geometry
from vxpy.utils import sphere


################################
# Abstract visual class

class AbstractVisual(ABC):
    description = ''

    interface = []

    # Display shaders
    _vertex_display = """
        attribute vec2 a_position;
        varying vec2 v_texcoord;

        void main() {
            v_texcoord = 0.5 + a_position / 2.0;
            gl_Position = vec4(a_position, 0.0, 1.0);
        }
    """

    _frag_display = """
        varying vec2 v_texcoord;

        uniform sampler2D u_texture;

        void main() {
            gl_FragColor = texture2D(u_texture, v_texcoord);
        }
    """

    _vertex_map = """
    """

    _parse_fun_prefix = 'parse_'

    def __init__(self, canvas):
        self.canvas: app.Canvas = canvas
        self.parameters: Dict[str, Any] = dict()
        self.custom_programs: Dict[str, gloo.Program] = dict()
        self.transform_uniforms = dict()

        self._buffer_shape = Config.Display[Def.DisplayCfg.window_height], \
                             Config.Display[Def.DisplayCfg.window_width] #self.canvas.physical_size[1], self.canvas.physical_size[0]
        self._out_texture = gloo.Texture2D(self._buffer_shape + (3,), format='rgb')
        self._out_fb = gloo.FrameBuffer(self._out_texture)
        self.frame = self._out_fb

        # Create display program: renders the out texture from FB to screen
        self.square = [[-1, -1], [-1, 1], [1, -1], [1, 1]]
        self._display_prog = gloo.Program(self._vertex_display, self._frag_display, count=4)
        self._display_prog['a_position'] = self.square
        self._display_prog['u_texture'] = self._out_texture

        gloo.set_state(depth_test=True)

    def __setattr__(self, key, value):
        # Catch programs being set and add them to dictionary (if they are not protected, i.e. default, programs)
        if not(hasattr(self, key)) and isinstance(value, gloo.Program) and not(key.startswith('_')):
            self.__dict__[key] = value
            self.__dict__['custom_programs'][key] = value
        else:
            self.__dict__[key] = value

    def apply_transform(self, program):
        """Set uniforms in transform_uniforms on program"""
        for u_name, u_value in self.transform_uniforms.items():
            program[u_name] = u_value

    @classmethod
    def load_shader(cls, filepath: str):
        if filepath.startswith('./'):
            # Use path relative to visual
            path = os.path.join(*cls.__module__.split('.')[:-1], filepath[2:])
        else:
            # Use absolute path to global shader folder
            path = os.path.join(Def.Path.Shader, filepath)

        with open(path, 'r') as f:
            code = f.read()

        return code

    def load_vertex_shader(self, filepath):
        return self.parse_vertex_shader(self.load_shader(filepath))

    def parse_vertex_shader(self, vert):
        return f'{self._vertex_map}\n{vert}'

    def trigger(self, trigger_fun):
        getattr(self, trigger_fun.__name__)()

    def update(self, _update_verbosely=True, **params):
        """
        Method to update stimulus parameters.

        Is called by default to update stimulus parameters.
        May be reimplemented in subclass.
        """

        if not(bool(params)):
            return

        # Write new value to parameters dictionary
        for key, value in params.items():
            # (Optional) parsing through custom function
            if hasattr(self, f'{self._parse_fun_prefix}{key}'):
                value = getattr(self, f'{self._parse_fun_prefix}{key}')(value)
            # Save to parameters
            self.parameters[key] = value

        # (optional) Logging
        if _update_verbosely:
            Logging.write(Logging.INFO,
                          f'Update visual {self.__class__.__name__}. '
                          'Set ' + ' '.join([f'{key}: {value}' for key, value in self.parameters.items()]))

        # Update program uniforms from parameters
        for program_name, program in self.custom_programs.items():
            for key, value in self.parameters.items():
                if key in program:
                    program[key] = value

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """Method to initialize and reset all parameters."""

    @abstractmethod
    def draw(self, dt):
        """Method to be implemented by BaseVisual class (BaseVisual, SphericalVisual, PlanarVisual, ...)."""

    @abstractmethod
    def render(self, dt):
        """Method to be implemented in final visual."""


class BaseVisual(AbstractVisual, ABC):

    _vertex_map = """
    uniform mat4  u_model;
    uniform mat4  u_view;
    uniform mat4  u_projection;
    
    vec4 transform_position(vec3 position) {
    
        vec4 pos = vec4(position, 1.0);
        pos = u_projection * u_view * u_model * pos;
        
        return pos;
    }
    """

    def __init__(self, *args, **kargs):
        AbstractVisual.__init__(self, *args, **kargs)

    def draw(self, dt):

        self.model = np.dot(transforms.rotate(-90, (1, 0, 0)), transforms.rotate(90, (0, 1, 0)))
        self.translate = 5
        self.view = transforms.translate((0, 0, -self.translate))

        self.transform_uniforms['u_view'] = self.view
        self.transform_uniforms['u_model'] = self.model

        self.apply_zoom()

        self.render(dt)

    def apply_zoom(self):
        gloo.set_viewport(0, 0, self.canvas.physical_size[0], self.canvas.physical_size[1])
        self.projection = transforms.perspective(45.0, self.canvas.size[0] / float(self.canvas.size[1]), 1.0, 1000.0)
        self.transform_uniforms['u_projection'] = self.projection


################################
# Spherical stimulus class

class SphericalVisual(AbstractVisual, ABC):

    # Standard transforms of sphere for 4-way display configuration
    _vertex_map = """
        uniform mat2 u_mapcalib_aspectscale;
        uniform vec2 u_mapcalib_scale;
        uniform mat4 u_mapcalib_translation;
        uniform mat4 u_mapcalib_projection;
        uniform mat4 u_mapcalib_rotate_elev;
        uniform mat4 u_mapcalib_inv_rotate_elev;
        uniform mat4 u_mapcalib_rotate_z;
        uniform mat4 u_mapcalib_rotate_x;
        uniform vec2 u_mapcalib_translate2d;
        uniform mat2 u_mapcalib_rotate2d;


        vec4 transform_position(vec3 position) {
            // Final position
            vec4 pos = vec4(position, 1.0);
            
            // Azimuth rotation (here around z axis)
            pos = u_mapcalib_rotate_z * pos;
            
            // 90 degrees in x axis
            pos = u_mapcalib_rotate_x * pos;
                        
            // Change elevation (here around x axis)
            pos = u_mapcalib_rotate_elev * pos;
            
            // Translate along z
            pos = u_mapcalib_translation * pos;
            
            // Project
            pos = u_mapcalib_projection * pos;
            
            // Flip direction for x (correct mirror inversion) 
            pos.x *= -1.;
            
            // 2D transforms (AFTER 3D projection!)
            pos = vec4(((u_mapcalib_rotate2d * pos.xy) * u_mapcalib_scale  + u_mapcalib_translate2d * pos.w) * u_mapcalib_aspectscale, pos.z, pos.w);
                
            return pos;
        }
    """

    _sphere_vert = """
        attribute vec3 a_position;
         
        varying vec3 v_position;
        varying vec4 v_map_position;
        
        void main() {
            v_map_position = transform_position(a_position);
            gl_Position = v_map_position;
            v_position = a_position;
        }
    """

    # Mask fragment shader
    _mask_frag = """
        uniform int u_part;
        
        varying vec3 v_position;
        varying vec4 v_map_position;
        void main() {
        
            gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0);

            //gl_FragColor = vec4(1.0-abs(v_position.z), abs(v_position.z)/2.0, 0.0, 1.0); 
            //gl_FragColor = vec4((-v_position.z+1.0)/2.0, (v_position.z+1.0)/2.0, 0.0, 1.0);
            //gl_FragColor = vec4(v_position.x, v_position.y, v_position.z, 1.0);
        }
    """

    # Out shaders
    _out_vert = """
        attribute vec2 a_position;
        varying vec2 v_texcoord;

        void main() {
            v_texcoord = 0.5 + a_position / 2.0;
            gl_Position = vec4(a_position, 0.0, 1.0);
        }
    """
    _out_frag = """
        uniform int u_part;
        
        varying vec2 v_texcoord;

        uniform sampler2D u_raw_texture;
        uniform sampler2D u_mask_texture;
        uniform sampler2D u_out_texture;

        void main() {
                    
            vec3 out_tex = texture2D(u_out_texture, v_texcoord).xyz;
            vec3 raw = texture2D(u_raw_texture, v_texcoord).xyz;
            float mask = texture2D(u_mask_texture, v_texcoord).x;
            
            if(mask > 0.0) {
                gl_FragColor = vec4(raw * mask, 1.0);
            } else {
                gl_FragColor = vec4(out_tex, 1.0);
            }
            
        }
    """

    def __init__(self, *args, **kwargs):
        AbstractVisual.__init__(self, *args, **kwargs)

        # Create mask model
        self._mask_model = sphere.UVSphere(azim_lvls=50,
                                           elev_lvls=50,
                                           azimuth_range=np.pi / 2,
                                           upper_elev=np.pi / 4,
                                           radius=1.0)
        self._mask_position_buffer = gloo.VertexBuffer(self._mask_model.a_position)
        self._mask_index_buffer = gloo.IndexBuffer(self._mask_model.indices)

        # Set textures and FBs
        self._mask_texture = gloo.Texture2D(self._buffer_shape + (3,), format='rgb')
        self._mask_depth_buffer = gloo.RenderBuffer(self._buffer_shape)
        self._mask_fb = gloo.FrameBuffer(self._mask_texture, self._mask_depth_buffer)

        self._raw_texture = gloo.Texture2D(self._buffer_shape + (3,), format='rgb')
        self._raw_depth_buffer = gloo.RenderBuffer(self._buffer_shape)
        self._raw_fb = gloo.FrameBuffer(self._raw_texture, self._raw_depth_buffer)

        self._display_texture = gloo.Texture2D(self._buffer_shape + (3,), format='rgb')
        self._display_fb = gloo.FrameBuffer(self._display_texture)

        # Create mask program: renders binary mask of quarter-sphere to FB
        sphere_vert = self.parse_vertex_shader(self._sphere_vert)
        self._mask_program = gloo.Program(sphere_vert, self._mask_frag)
        self._mask_program['a_position'] = self._mask_position_buffer

        # Create out program: renders the output texture to FB
        # by combining raw and mask textures
        # (to be saved and re-rendered in display program)
        # square = [[-1, -1], [-1, 1], [1, -1], [1, 1]]
        self._out_prog = gloo.Program(self._out_vert, self._out_frag, count=4)
        self._out_prog['a_position'] = self.square
        self._out_prog['u_raw_texture'] = self._raw_texture
        self._out_prog['u_mask_texture'] = self._mask_texture
        self._out_prog['u_out_texture'] = self._out_texture

        # Set clear color
        #gloo.set_clear_color('black')
        #gloo.set_clear_color('red')

    def draw(self, dt):
        gloo.clear()

        self.frame_time = dt

        win_width = Config.Display[Def.DisplayCfg.window_width]
        win_height = Config.Display[Def.DisplayCfg.window_height]
        # Set 2D scaling for aspect 1
        if win_height > win_width:
            u_mapcalib_aspectscale = np.eye(2) * np.array([1, win_width / win_height])
        else:
            u_mapcalib_aspectscale = np.eye(2) * np.array([win_height / win_width, 1])
        self.transform_uniforms['u_mapcalib_aspectscale'] = u_mapcalib_aspectscale

        # Make sure stencil testing is disabled and depth testing is enabled
        #gl.glDisable(gl.GL_STENCIL_TEST)
        gl.glEnable(gl.GL_DEPTH_TEST)

        # Clear raw stimulus buffer
        with self._raw_fb:
            gloo.clear()

        # Clear mask buffer
        with self._mask_fb:
            gloo.clear()

        with self._out_fb:
            gloo.clear()

        with self._display_fb:
            gloo.clear()

        for i in range(4):

            azim_orientation = Config.Display[Def.DisplayCfg.sph_view_azim_orient]
            azim_angle = Config.Display[Def.DisplayCfg.sph_view_azim_angle][i]

            # Set 3D transform
            distance = Config.Display[Def.DisplayCfg.sph_view_distance][i]
            fov = Config.Display[Def.DisplayCfg.sph_view_fov][i]
            view_scale = Config.Display[Def.DisplayCfg.sph_view_scale][i]
            elev_angle = Config.Display[Def.DisplayCfg.sph_view_elev_angle][i]
            radial_offset_scalar = Config.Display[Def.DisplayCfg.sph_pos_glob_radial_offset][i]

            # Set relative size
            self.transform_uniforms['u_mapcalib_scale'] = view_scale * np.array([1, 1])

            # 3D translation
            self.transform_uniforms['u_mapcalib_translation'] = transforms.translate((0, 0, -distance))

            # 3D projection
            self.transform_uniforms['u_mapcalib_projection'] = transforms.perspective(fov, 1., 0.1, 400.0)

            xy_offset = np.array([Config.Display[Def.DisplayCfg.glob_x_pos] * win_width / win_height,
                                  Config.Display[Def.DisplayCfg.glob_y_pos]])

            self.transform_uniforms['u_mapcalib_rotate_x'] = transforms.rotate(90, (1, 0, 0))

            # 3D elevation rotation
            self.transform_uniforms['u_mapcalib_rotate_elev'] = transforms.rotate(-elev_angle, (1, 0, 0))

            # 2D rotation around center of screen
            self.transform_uniforms['u_mapcalib_rotate2d'] = geometry.rotation2D(np.pi / 4 - np.pi / 2 * i)

            # 2D translation radially
            radial_offset = np.array([-np.real(1.j ** (.5 + i)), -np.imag(1.j ** (.5 + i))]) * radial_offset_scalar
            self.transform_uniforms['u_mapcalib_translate2d'] = radial_offset + xy_offset

            # Render 90 degree mask to mask buffer
            # (BEFORE further 90deg rotation)
            self.transform_uniforms['u_mapcalib_rotate_z'] = transforms.rotate(45 + azim_angle, (0,0,1))
            self.apply_transform(self._mask_program)
            self._mask_program['u_part'] = i
            with self._mask_fb:
                self._mask_program.draw('triangles', self._mask_index_buffer)

            # Apply 90*i degree rotation to actual spherical stimulus
            self.transform_uniforms['u_mapcalib_rotate_z'] = transforms.rotate(azim_orientation + 90 * i + azim_angle, (0, 0, 1))

            # And render actual stimulus sphere
            with self._raw_fb:
                # Important: only provide dt on first iteration.
                # Otherwise the final cumulative time is going to be ~4*dt (too high!)
                self.render(dt if i == 0 else 0.0)

            # Combine mask and raw texture into out_texture
            # (To optionally be saved to disk and rendered to screen)
            self._out_prog['u_part'] = i
            with self._out_fb:
                self._out_prog.draw('triangle_strip')

            with self._mask_fb:
                gloo.clear()

            with self._raw_fb:
                gloo.clear()

        self._display_prog.draw('triangle_strip')


################################
# Plane stimulus class

class PlanarVisual(AbstractVisual, ABC):

    _vertex_map = """
    uniform float u_mapcalib_xscale;
    uniform float u_mapcalib_yscale;
    uniform float u_mapcalib_xextent;
    uniform float u_mapcalib_yextent;
    uniform float u_mapcalib_small_side_size;
    uniform float u_mapcalib_glob_x_position;
    uniform float u_mapcalib_glob_y_position;
    
    vec4 transform_position(vec3 position) {
        vec4 pos = vec4(position.x * u_mapcalib_xscale * u_mapcalib_xextent + u_mapcalib_glob_x_position,
                        position.y * u_mapcalib_yscale * u_mapcalib_yextent + u_mapcalib_glob_y_position,
                        position.z, 
                        1.0);
        return pos;
    }
    
    vec2 real_position(vec3 position) {
        //vec2 pos = vec2((1.0 + position.x) / 2.0 * u_mapcalib_xextent * u_mapcalib_small_side_size,
        //                (1.0 + position.y) / 2.0 * u_mapcalib_yextent * u_mapcalib_small_side_size);
        vec2 pos = vec2(position.x / 2.0 * u_mapcalib_xextent * u_mapcalib_small_side_size,
                        position.y / 2.0 * u_mapcalib_yextent * u_mapcalib_small_side_size);
        return pos;
    }
    
    vec2 norm_position(vec3 position) {

        vec2 pos = vec2((1.0 + position.x) / 2.0,
                        (1.0 + position.y) / 2.0);
        return pos;
    }
    
    """

    def __init__(self, *args, **kwargs):
        AbstractVisual.__init__(self, *args, **kwargs)

    def draw(self, dt):
        gloo.clear()

        # Construct vertices
        height = Config.Display[Def.DisplayCfg.window_height]
        width = Config.Display[Def.DisplayCfg.window_width]

        # Set aspect scale to square
        if width > height:
            self.u_mapcalib_xscale = height/width
            self.u_mapcalib_yscale = 1.
        else:
            self.u_mapcalib_xscale = 1.
            self.u_mapcalib_yscale = width/height

        # Set 2d translation
        self.u_mapcalib_glob_x_position = Config.Display[Def.DisplayCfg.glob_x_pos]
        self.u_mapcalib_glob_y_position = Config.Display[Def.DisplayCfg.glob_y_pos]

        # Extents
        self.u_mapcalib_xextent = Config.Display[Def.DisplayCfg.pla_xextent]
        self.u_mapcalib_yextent = Config.Display[Def.DisplayCfg.pla_yextent]

        # Set real world size multiplier [mm]
        # (PlanarVisual's positions are normalized to the smaller side of the screen)
        self.u_mapcalib_small_side_size = Config.Display[Def.DisplayCfg.pla_small_side]

        # Set uniforms
        self.transform_uniforms['u_mapcalib_xscale'] = self.u_mapcalib_xscale
        self.transform_uniforms['u_mapcalib_yscale'] = self.u_mapcalib_yscale
        self.transform_uniforms['u_mapcalib_xextent'] = self.u_mapcalib_xextent
        self.transform_uniforms['u_mapcalib_yextent'] = self.u_mapcalib_yextent
        self.transform_uniforms['u_mapcalib_small_side_size'] = self.u_mapcalib_small_side_size
        self.transform_uniforms['u_mapcalib_glob_x_position'] = self.u_mapcalib_glob_x_position
        self.transform_uniforms['u_mapcalib_glob_y_position'] = self.u_mapcalib_glob_y_position

        # Call the rendering function of the subclass
        try:
            # Render to buffer
            with self._out_fb:
                self.render(dt)

            # Render to display
            self._display_prog.draw('triangle_strip')

        except Exception as exc:
            import traceback
            print(traceback.print_exc())