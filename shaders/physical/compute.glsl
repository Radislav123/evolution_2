#version 460
#extension GL_ARB_bindless_texture : require


// Переменные, которые почти не меняются или меняются редко
uniform uint u_cell_substance_count;

uniform ivec3 u_world_shape;
uniform vec3 u_gravity_vector;

// Переменные, которые могу меняться каждый кадр
// При tps == 1000 uint32 хватит примерно на 49.7 суток непрерывной симуляции
uniform uint u_world_age;


layout(local_size_x = block_size_x, local_size_y = block_size_y, local_size_z = block_size_z) in;

layout(std430, binding = 0) readonly restrict buffer WorldRead {
    usampler3D handles[];
} u_world_read;
layout(std430, binding = 1) writeonly restrict buffer WorldWrite {
    uimage3D handles[];
} u_world_write;


void main() {
    ivec3 read_position = ivec3(gl_GlobalInvocationID);
    ivec3 write_position = read_position;

    bool move = true;
    if (move && u_world_age % 50 == 0) {
        write_position = (write_position + ivec3(u_gravity_vector)) % u_world_shape;
    }

    bool next_layer_filled = true;
    for (uint layer_index = 0u; layer_index < u_cell_substance_count && next_layer_filled; layer_index++) {
        uvec4 packed_layer = texelFetch(u_world_read.handles[layer_index], read_position, 0);
        next_layer_filled = bool(bitfieldExtract(packed_layer.r, 30, 1));

        imageStore(u_world_write.handles[layer_index], write_position, packed_layer);
    }
}
