#version 460
#extension GL_ARB_bindless_texture : require


// Переменные, которые почти не меняются или меняются редко
uniform uint u_cell_substance_count;
uniform int u_world_update_period;

uniform ivec3 u_world_shape;
uniform vec3 u_gravity_vector;

// Переменные, которые могу меняться каждый кадр
// При tps == 1000 uint32 хватит примерно на 49.7 суток непрерывной симуляции
// uniform uint u_world_age;


layout(local_size_x = block_size_x, local_size_y = block_size_y, local_size_z = block_size_z) in;

layout(std430, binding = 0) readonly restrict buffer WorldRead {
    usampler3D handles[];
} u_world_read;
layout(std430, binding = 1) writeonly restrict buffer WorldWrite {
    uimage3D handles[];
} u_world_write;

const int zero_offset_10_bit = int(pow(2, 10 - 1));
// Коэффициент поправки необходим для более точного хранения
const float momentum_coeff = 100;


void main() {
    ivec3 read_position = ivec3(gl_GlobalInvocationID);
    ivec3 write_position = read_position;

    bool next_layer_filled = true;
    for (uint layer_index = 0u; layer_index < u_cell_substance_count && next_layer_filled; layer_index++) {
        uvec4 packed_layer = texelFetch(u_world_read.handles[layer_index], read_position, 0);

        uint substance_id = bitfieldExtract(packed_layer.r, 0, 15);
        int quantity = int(bitfieldExtract(packed_layer.r, 15, 15));
        next_layer_filled = bool(bitfieldExtract(packed_layer.r, 30, 1));

        // momentum - импульс одной молекулы вещества в ячейке
        vec3 momentum = (vec3(
        bitfieldExtract(packed_layer.g, 0, 10),
        bitfieldExtract(packed_layer.g, 10, 10),
        bitfieldExtract(packed_layer.g, 20, 10)
        ) - zero_offset_10_bit) / momentum_coeff;

        momentum += u_gravity_vector * u_world_update_period;
        // todo: Добавить деление momentum на массу молекулы
        write_position = ivec3(write_position + momentum * u_world_update_period) % u_world_shape;

        momentum *= momentum_coeff;
        packed_layer.g = uint(momentum.x + zero_offset_10_bit)
        | (uint(momentum.y + zero_offset_10_bit) << 10)
        | (uint(momentum.z + zero_offset_10_bit) << 20);
        imageStore(u_world_write.handles[layer_index], write_position, packed_layer);
    }
}
