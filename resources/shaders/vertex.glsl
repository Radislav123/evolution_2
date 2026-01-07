#version 460

uniform mat4 u_vp;

in vec3 in_position;
in vec3 in_normal;
in vec3 in_instance_position;
in vec4 in_instance_color;

out vec3 v_normal;
out vec3 v_vertex_position;
out vec3 v_instance_position;
out vec4 v_color;

void main() {
    // todo: collapse to one line
    v_vertex_position = in_position * 0.999 + in_instance_position;
    gl_Position = u_vp * vec4(v_vertex_position, 1);

    v_normal = in_normal;
    v_instance_position = in_instance_position;
    v_color = in_instance_color;
}