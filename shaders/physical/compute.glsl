#version 460
#extension GL_ARB_bindless_texture : require


// Переменные, которые почти не меняются или меняются редко
uniform uint u_connected_texture_count;

uniform ivec3 u_world_shape;
uniform vec3 u_gravity_vector;

// Переменные, которые могу меняться каждый кадр
// При tps == 1000 uint32 хватит примерно на 49.7 суток непрерывной симуляции
uniform uint u_world_age;


layout(local_size_x = block_size_x, local_size_y = block_size_y, local_size_z = block_size_z) in;

layout(std430, binding = 0) readonly restrict buffer SubstancesRead {
    usampler3D handles[];
} u_substances_read;
layout(std430, binding = 1) writeonly restrict buffer SubstancesWrite {
    uimage3D handles[];
} u_substances_write;

layout(std430, binding = 2) readonly restrict buffer QuanititesRead {
    usampler3D handles[];
} u_quanitites_read;
layout(std430, binding = 3) writeonly restrict buffer QuanititesWrite {
    uimage3D handles[];
} u_quanitites_write;

void main() {
    ivec3 read_position = ivec3(gl_GlobalInvocationID);
    ivec3 write_position = read_position;

    bool move = true;
    if (move && u_world_age % 50 == 0) {
        write_position = (write_position + ivec3(u_gravity_vector)) % u_world_shape;
    }

    for (uint texture_index = 0u; texture_index < u_connected_texture_count; texture_index++) {
        uvec4 substances_4 = texelFetch(u_substances_read.handles[texture_index], read_position, 0);
        uvec4 quantities_4 = texelFetch(u_quanitites_read.handles[texture_index], read_position, 0);

        imageStore(u_substances_write.handles[texture_index], write_position, substances_4);
        imageStore(u_quanitites_write.handles[texture_index], write_position, quantities_4);
    }
}
