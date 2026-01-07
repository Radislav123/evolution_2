#version 460

uniform vec3 u_world_shape_min;
uniform vec3 u_world_shape_max;

in vec3 v_normal;
in vec3 v_instance_position;
in vec4 v_color;

out vec4 f_color;

void main() {
    f_color = v_color;
    //    f_color = vec4(0, 0, 0, 0.1);
    //    f_color[3] = 1;
    if (v_instance_position == vec3(0, 0, 0)) {
        f_color = vec4(0.8, 0.0, 0.0, 1);
    }
    if (v_instance_position == vec3(0, 0, -1)) {
        f_color = vec4(0.0, 0.8, 0.0, 1);
    }
    // gl_FragDepth = 0.5;
}
