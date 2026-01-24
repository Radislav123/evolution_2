#version 460
#extension GL_ARB_bindless_texture : require

const uvec3 cell_shape = uvec3(cell_size_x, cell_size_y, cell_size_z);
const uvec3 cell_cache_shape = uvec3(cell_size_x + 2, cell_size_y + 2, cell_size_z + 2);

layout(local_size_x = cell_shape.x, local_size_y = cell_shape.y, local_size_z = cell_shape.z) in;
// Содержит юниты ячейки и юниты соседних ячеек в один слой
shared uvec4 cell_cache[cell_cache_shape.x][cell_cache_shape.y][cell_cache_shape.z];

const uint cell_size = cell_shape.x * cell_shape.y * cell_shape.z;
const uint cell_cache_size = cell_cache_shape.x * cell_cache_shape.y * cell_cache_shape.z;


// Переменные, которые почти не меняются или меняются редко
uniform int u_world_update_period;

uniform ivec3 u_world_unit_shape;
uniform vec3 u_gravity_vector;

// Переменные, которые могу меняться каждый кадр
// При tps == 1000 uint32 хватит примерно на 49.7 суток непрерывной симуляции
uniform uint u_world_age;


layout(std430, binding = 0) readonly restrict buffer WorldRead {
    usampler3D handles[];
} u_world_read;
layout(std430, binding = 1) writeonly restrict buffer WorldWrite {
    uimage3D handles[];
} u_world_write;

const float zero_offset_10_bit = pow(2, 10 - 1);
// Коэффициент поправки необходим для более точного хранения
const float momentum_coeff = 100.0;


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

// todo: Внедрить проверку на переполнение записываемых величин
uvec4 pack_unit(Unit unit) {
    uvec4 packed_unit = uvec4(0);

    packed_unit.r = unit.substance | (unit.quantity << 15);

    uvec3 casted_momentum = uvec3(unit.momentum * momentum_coeff + zero_offset_10_bit);
    packed_unit.g = casted_momentum.x
    | (casted_momentum.y << 10)
    | (casted_momentum.z << 20);

    return packed_unit;
}


void main() {
    // todo: remove stubs;
    u_world_update_period;
    u_world_unit_shape;
    u_gravity_vector;

    ivec3 global_position = ivec3(gl_GlobalInvocationID);
    uint chunk_index = 0;

    for (uint index = gl_LocalInvocationIndex; index < cell_cache_size; index += cell_size) {
        ivec3 cache_position = ivec3(
        index % cell_cache_shape.x,
        (index % (cell_cache_shape.x * cell_cache_shape.y)) / cell_cache_shape.x,
        index / (cell_cache_shape.x * cell_cache_shape.y)
        );
        ivec3 read_position = (cache_position + ivec3(gl_WorkGroupID * cell_shape) - 1 + u_world_unit_shape) % u_world_unit_shape;

        cell_cache[cache_position.x][cache_position.y][cache_position.z] = texelFetch(u_world_read.handles[chunk_index], read_position, 0);
    }

    memoryBarrierShared();
    barrier();

    ivec3 cache_position = ivec3(gl_LocalInvocationID) + 1;
    Unit unit = unpack_unit(cell_cache[cache_position.x][cache_position.y][cache_position.z]);

    ivec3 write_position = global_position;

    if (u_world_age % 50 == 0 && u_world_age > 50) {
        write_position = (write_position + ivec3(sign(u_gravity_vector)) + u_world_unit_shape) % u_world_unit_shape;
    }
    imageStore(u_world_write.handles[chunk_index], write_position, pack_unit(unit));
}
