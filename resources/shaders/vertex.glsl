#version 460

uniform mat4 u_mvp;

in vec3 in_position;
in vec3 in_normal;
in vec3 in_instance_position;
in vec4 in_instance_color;

out vec3 v_normal;
out vec3 v_instance_position;
out vec4 v_color;

void main() {
    gl_Position = u_mvp * vec4(in_position * 0.9 + in_instance_position, 1);

    v_normal = in_normal;
    v_instance_position = in_instance_position;
    v_color = in_instance_color;
}