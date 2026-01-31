#version 460
#extension GL_ARB_bindless_texture : require


#include physical_constants
#include packing_constants

#include cell_packing
#include unit_packing


const ivec3 cell_group_shape = cell_group_shape_placeholder;
const ivec3 cell_cache_shape = cell_group_shape + 2;
const int cell_group_size = cell_group_shape.x * cell_group_shape.y * cell_group_shape.z;
const int cell_cache_size = cell_cache_shape.x * cell_cache_shape.y * cell_cache_shape.z;

layout(local_size_x = cell_group_shape.x, local_size_y = cell_group_shape.y, local_size_z = cell_group_shape.z) in;
shared Cell cell_cache[cell_cache_shape.x][cell_cache_shape.y][cell_cache_shape.z];

const ivec3 cell_offsets[7] = ivec3[7](
ivec3(0, 0, 0),
ivec3(-1, 0, 0),
ivec3(1, 0, 0),
ivec3(0, -1, 0),
ivec3(0, 1, 0),
ivec3(0, 0, -1),
ivec3(0, 0, 1)
);


// Переменные, которые почти не меняются или меняются редко
uniform int u_world_update_period;
uniform ivec3 u_gravity_vector;

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


void main() {
    ivec3 global_group_posiiton = ivec3(gl_WorkGroupID);
    ivec3 global_cell_position = ivec3(gl_GlobalInvocationID);
    int local_cell_index = int(gl_LocalInvocationIndex);
    uint chunk_index = 0;

    for (uint cell_index = local_cell_index; cell_index < cell_cache_size; cell_index += cell_group_size) {
        ivec3 cell_cache_position = ivec3(
        cell_index % cell_cache_shape.x,
        (cell_index % (cell_cache_shape.x * cell_cache_shape.y)) / cell_cache_shape.x,
        cell_index / (cell_cache_shape.x * cell_cache_shape.y)
        );
        ivec3 read_position = (cell_cache_position + ivec3(global_group_posiiton * cell_group_shape) - 1 + world_shape) % world_shape;

        cell_cache[cell_cache_position.x][cell_cache_position.y][cell_cache_position.z] = unpack_cell(texelFetch(u_world_read.handles[chunk_index], read_position, 2));
    }

    memoryBarrierShared();
    barrier();

    ivec3 cell_cache_position = ivec3(gl_LocalInvocationID);
    Cell cell = cell_cache[cell_cache_position.x][cell_cache_position.y][cell_cache_position.z];

    for (int unit_index = 0; unit_index < cell.filled_units; unit_index++) {
        ivec3 local_unit_position = ivec3(
        unit_index % cell_shape.x,
        (unit_index % (cell_shape.x * cell_shape.y)) / cell_shape.x,
        unit_index / (cell_shape.x * cell_shape.y)
        );
        ivec3 global_unit_position = global_cell_position * cell_shape + local_unit_position;
        Unit unit = unpack_unit(texelFetch(u_world_read.handles[chunk_index], global_unit_position, 0));

        unit.momentum += u_gravity_vector * u_world_update_period;
        // todo: Заменить 1 на массу молекулы (хранить ее в юните, чтобы не читать лишний раз?)
        // todo: При (momentum.d == request_min_momentum * molecule_mass) перемещать раз в 100 тиков, при повышении импульса перемещать чаще?
        if (any(greaterThanEqual(abs(unit.momentum), request_min_momentum * 1))) {
            unit.substance = 1u;
        }

        imageStore(u_world_unit_write.handles[chunk_index], global_unit_position, pack_unit(unit));
    }

    imageStore(u_world_cell_write.handles[chunk_index], global_cell_position, pack_cell(cell));
}
