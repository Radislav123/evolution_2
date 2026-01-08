#version 460

uniform mat4 u_vp;

in vec3 in_normal;
in vec3 in_position;
in ivec4 in_instance_position;
in vec4 in_instance_color;

flat out ivec3 v_instance_position;
out vec3 v_normal;
out vec4 v_color;

void main() {
    v_normal = in_normal;
    v_instance_position = ivec3(in_instance_position.xyz);
    v_color = in_instance_color;

    gl_Position = u_vp * vec4(in_position * 0.999999999 + v_instance_position, 1);
}
