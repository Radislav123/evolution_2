#version 460
#extension GL_ARB_bindless_texture : require

const ivec3 cell_shape = ivec3(cell_size_d, cell_size_d, cell_size_d);
const ivec3 block_shape = ivec3(block_size_d, block_size_d, block_size_d);
const int cell_size = cell_shape.x * cell_shape.y * cell_shape.z;

layout(local_size_x = cell_shape.x, local_size_y = cell_shape.y, local_size_z = cell_shape.z) in;
// performance: Хранить данные распакованными?
shared uvec4 cell_cache[7];
shared uvec4 unit_cache[7][cell_size];
const ivec3 cell_offsets[7] = ivec3[7](
ivec3(0, 0, 0),
ivec3(-1, 0, 0),
ivec3(1, 0, 0),
ivec3(0, -1, 0),
ivec3(0, 1, 0),
ivec3(0, 0, -1),
ivec3(0, 0, 1)
);
const ivec3 unit_offsets[7] = ivec3[7](
cell_offsets[0] * cell_shape,
cell_offsets[1] * cell_shape,
cell_offsets[2] * cell_shape,
cell_offsets[3] * cell_shape,
cell_offsets[4] * cell_shape,
cell_offsets[5] * cell_shape,
cell_offsets[6] * cell_shape
);


// Переменные, которые почти не меняются или меняются редко
uniform int u_world_update_period;

uniform ivec3 u_world_shape;
uniform ivec3 u_world_unit_shape;
uniform vec3 u_gravity_vector;

// Переменные, которые могу меняться каждый кадр
// Порядок и дополнения до 16 байт должны совпадать с тем, что обхявлено в python-коде
layout(std140, binding = 2) uniform PhysicsBuffer {
// При tps == 1000 uint32 хватит примерно на 49.7 суток непрерывной симуляции
    int u_world_age;
    ivec3 u_padding_0;
};


layout(std430, binding = 0) readonly restrict buffer WorldRead {
    usampler3D handles[];
} u_world_read;
layout(std430, binding = 1) writeonly restrict buffer WorldCellWrite {
    uimage3D handles[];
} u_world_cell_write;
layout(std430, binding = 2) writeonly restrict buffer WorldBlockWrite {
    uimage3D handles[];
} u_world_block_write;
layout(std430, binding = 3) writeonly restrict buffer WorldUnitWrite {
    uimage3D handles[];
} u_world_unit_write;


#include physical_constants
#include packing_constants
#include cell
#include unit


void main() {
    // Позиция ячейки в текстуре 2-го уровня
    ivec3 global_cell_position = ivec3(gl_WorkGroupID);
    // Позиция юнита в текстуре
    ivec3 global_unit_position = ivec3(gl_GlobalInvocationID);
    // Позиция юнита в ячейке
    ivec3 local_unit_position = ivec3(gl_LocalInvocationID);
    int local_index = int(gl_LocalInvocationIndex);
    uint chunk_index = 0;

    // performance: Считывать данные своего юнита, определять направление момента, на основе этого определять, какие соседи нужны, и грузить только необходимых соседей?
    // performance: Создавать потоков на каждый считываемый юнит (4х4х4х7), а вычисления проводить только на действительных (4х4х4)?
    // performance: Во втором слое завести счетчик, показывающий сколько юнитов заполнено
    for (uint cell_index = 0u; cell_index < 7u; cell_index++) {
        ivec3 read_position = (global_unit_position + unit_offsets[cell_index] + u_world_unit_shape) % u_world_unit_shape;
        unit_cache[cell_index][local_index] = texelFetch(u_world_read.handles[chunk_index], read_position, 0);
    }
    if (local_index < 7) {
        ivec3 read_position = (global_cell_position + unit_offsets[local_index] + u_world_shape) % u_world_shape;
        cell_cache[local_index] = texelFetch(u_world_read.handles[chunk_index], read_position, 2);
    }

    memoryBarrierShared();
    barrier();

    Unit unit = unpack_unit(unit_cache[0][local_index]);

    bool is_empty = (local_index < 32) ?
    ((cell_cache[0].x >> local_index) & 1u) == 0u :
    ((cell_cache[0].y >> (local_index - 32u)) & 1u) == 0u;
    if (is_empty) {
        // тут можно всякое делать
    }

    unit.momentum += u_gravity_vector * u_world_update_period;
    if (u_world_age % 100 == 0) {
        //        global_unit_position = (global_unit_position + ivec3(sign(unit.momentum)) * cell_shape + u_world_unit_shape) % u_world_unit_shape;
    }

    imageStore(u_world_unit_write.handles[chunk_index], global_unit_position, pack_unit(unit));
    // todo: Перенести эту запись в свой отдельный шейдер
    imageStore(u_world_cell_write.handles[chunk_index], global_cell_position, cell_cache[0]);
}
