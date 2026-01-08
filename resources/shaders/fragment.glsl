#version 460

uniform float u_near;
uniform float u_far;
uniform vec3 u_world_min;
uniform vec3 u_world_max;

flat in ivec3 v_instance_position;
in vec3 v_normal;
in vec4 v_color;

out vec4 f_color;

void main() {
    float inner_face_transparency_coeff = 0.7;
    vec3 neigbour = v_instance_position + v_normal;
    if ((neigbour.x >= u_world_min.x && neigbour.x <= u_world_max.x)
    && (neigbour.y >= u_world_min.y && neigbour.y <= u_world_max.y)
    && (neigbour.z >= u_world_min.z && neigbour.z <= u_world_max.z)) {
        f_color = vec4(v_color.rgb, v_color.a * inner_face_transparency_coeff);
    } else {
        f_color = v_color;
    }
}
