#version 460

uniform ivec3 u_world_shape_min;
uniform ivec3 u_world_shape_max;
uniform vec3 u_view_position;
uniform int u_render_transparent;

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
    u_world_shape_min;
    u_world_shape_max;
    //    f_color = vec4(0, 0, 0, 0.1);
    //    //    f_color[3] = 1;
    //    if (v_instance_position == vec3(0, 0, 0)) {
    //        f_color = vec4(0.8, 0.0, 0.0, 1);
    //    }
    //    if (v_instance_position == vec3(0, 0, -1)) {
    //        f_color = vec4(0.0, 0.8, 0.0, 1);
    //    }
}
