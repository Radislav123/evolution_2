#version 460
#extension GL_ARB_bindless_texture : require


// Переменные, которые почти не меняются или меняются редко
uniform int u_world_update_period;

uniform ivec3 u_world_unit_shape;
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
const uint momentum_coeff = 100;


struct Unit {
    uint substance;
    uint quantity;
    vec3 momentum;
};

Unit unpack_unit(uvec4 packed_unit) {
    Unit unit;

    unit.substance = bitfieldExtract(packed_unit.r, 0, 15);
    unit.quantity = bitfieldExtract(packed_unit.r, 15, 15);

    // momentum - импульс одной молекулы вещества
    unit.momentum = (vec3(
    bitfieldExtract(packed_unit.g, 0, 10),
    bitfieldExtract(packed_unit.g, 10, 10),
    bitfieldExtract(packed_unit.g, 20, 10)
    ) - zero_offset_10_bit) / momentum_coeff;

    return unit;
}

uvec4 pack_unit(Unit unit) {
    uvec4 packed_unit;

    packed_unit.r = unit.substance | (unit.quantity << 15);

    uvec3 packed_momentum = uvec3(unit.momentum + zero_offset_10_bit) * momentum_coeff;
    packed_unit.g = packed_momentum.x
    | (packed_momentum.y << 10)
    | (packed_momentum.z << 20);

    return packed_unit;
}


void main() {
    // todo: remove stubs;
    u_world_update_period;
    u_world_unit_shape;
    u_gravity_vector;

    ivec3 read_position = ivec3(gl_GlobalInvocationID);
    ivec3 write_position = read_position;
    uint chunk_index = 0;

    Unit unit = unpack_unit(texelFetch(u_world_read.handles[chunk_index], read_position, 0));

    imageStore(u_world_write.handles[chunk_index], write_position, pack_unit(unit));
}
