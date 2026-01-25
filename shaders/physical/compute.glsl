#version 460
#extension GL_ARB_bindless_texture : require

const uvec3 cell_shape = uvec3(cell_size_d, cell_size_d, cell_size_d);
const uint cell_size = cell_shape.x * cell_shape.y * cell_shape.z;

layout(local_size_x = cell_shape.x, local_size_y = cell_shape.y, local_size_z = cell_shape.z) in;
// performance: Хранить данные распакованными?
shared uvec4 cell_cache[7][cell_size];
const ivec3 cell_offsets[7] = ivec3[7](
ivec3(0, 0, 0),
ivec3(-cell_shape.x, 0, 0),
ivec3(cell_shape.x, 0, 0),
ivec3(0, -cell_shape.y, 0),
ivec3(0, cell_shape.y, 0),
ivec3(0, 0, -cell_shape.z),
ivec3(0, 0, cell_shape.z)
);


// Переменные, которые почти не меняются или меняются редко
uniform int u_world_update_period;

uniform ivec3 u_world_unit_shape;
uniform vec3 u_gravity_vector;

// Переменные, которые могу меняться каждый кадр
// Порядок и дополнения до 16 байт должны совпадать с тем, что обхявлено в python-коде
layout(std140, binding = 3) uniform CameraBuffer {
// При tps == 1000 uint32 хватит примерно на 49.7 суток непрерывной симуляции
    int u_world_age;
    ivec3 u_padding_0;
};


layout(std430, binding = 0) readonly restrict buffer WorldRead {
    usampler3D handles[];
} u_world_read;
layout(std430, binding = 1) writeonly restrict buffer WorldWrite {
    uimage3D handles[];
} u_world_write;

const float zero_offset_10_bit = pow(2, 10 - 1);
const uint mask_9_bit  = (1u << 9) - 1u;
const uint mask_10_bit = (1u << 10) - 1u;
const uint mask_15_bit = (1u << 15) - 1u;
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

    packed_unit.r = (unit.substance & mask_15_bit) | ((unit.quantity & mask_15_bit) << 15);

    uvec3 casted_momentum = uvec3(clamp(unit.momentum * momentum_coeff + zero_offset_10_bit, 0.0, float(mask_10_bit)));
    packed_unit.g = (casted_momentum.x & mask_10_bit)
    | ((casted_momentum.y & mask_10_bit) << 10)
    | ((casted_momentum.z & mask_10_bit) << 20);

    return packed_unit;
}


void main() {
    // Позиция юнита в текстуре
    ivec3 global_position = ivec3(gl_GlobalInvocationID);
    // Позиция юнита в ячейке
    ivec3 local_position = ivec3(gl_LocalInvocationID);
    int local_index = int(gl_LocalInvocationIndex);
    uint chunk_index = 0;

    // performance: Считывать данные своего юнита, определять направление момента, на основе этого определять, какие соседи нужны, и грузить только необходимых соседей?
    // performance: Во втором слое завести счетчик, показывающий сколько юнитов заполнено
    for (uint cell_index = 0; cell_index < 7; cell_index++) {
        ivec3 read_position = (global_position + cell_offsets[cell_index] + u_world_unit_shape) % u_world_unit_shape;
        cell_cache[cell_index][local_index] = texelFetch(u_world_read.handles[chunk_index], read_position, 0);
    }

    memoryBarrierShared();
    barrier();

    Unit unit = unpack_unit(cell_cache[0][local_index]);
    imageStore(u_world_write.handles[chunk_index], global_position, pack_unit(unit));
}
