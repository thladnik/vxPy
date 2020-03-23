// f_checkerboard.glsl

const float c_pi = 3.14159265359;

uniform int u_checker_rows;
uniform int u_checker_cols;

varying float v_azimuth;
varying float v_elevation;

void main()
{

    // Construct checkerboard
    float c = sin(float(u_checker_cols) * v_azimuth) * sin(float(u_checker_rows) * v_elevation);

    // Thresholding
    if (c > 0) {
       c = 1.0;
    } else {
         c = 0.0;
    }

    // Final color
    gl_FragColor = vec4(c, c, c, 1.0);;

}