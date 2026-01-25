#version 460

in vec2 in_vertex_position;

void main() {
    gl_Position = vec4(in_vertex_position, 0.0, 1.0);
}
