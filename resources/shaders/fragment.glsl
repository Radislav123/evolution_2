#version 460

uniform vec3 u_view_position;
uniform int u_render_transparent;
uniform float u_near;
uniform float u_far;

in vec3 v_normal;
in vec3 v_vertex_position;
in vec3 v_instance_position;
in vec4 v_color;

out vec4 f_color;

void main() {
    f_color = v_color;

    // Чтобы показать, что переменные используются и их не нужно выкидывать
    u_render_transparent;
    u_view_position;
}
