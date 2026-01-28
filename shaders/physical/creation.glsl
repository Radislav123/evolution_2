#version 460
#extension GL_ARB_bindless_texture : require


#include physical_constants
#include packing_constants


layout(local_size_x = cell_shape.x, local_size_y = cell_shape.y, local_size_z = cell_shape.z) in;


layout(std430, binding = 1) writeonly restrict buffer WorldCellWrite {
    uimage3D handles[];
} u_world_cell_write;
layout(std430, binding = 2) writeonly restrict buffer WorldBlockWrite {
    uimage3D handles[];
} u_world_block_write;
layout(std430, binding = 3) writeonly restrict buffer WorldUnitWrite {
    uimage3D handles[];
} u_world_unit_write;


#include cell_packing
#include unit_packing


void main() {
    // Позиция ячейки в текстуре 2-го уровня
    ivec3 global_cell_position = ivec3(gl_WorkGroupID);
    // Позиция юнита в текстуре
    ivec3 global_unit_position = ivec3(gl_GlobalInvocationID);
    uint chunk_index = 0;

    float sphere_radius = float(min(world_unit_shape.x, min(world_unit_shape.y, world_unit_shape.z))) / 2.0;
    float radius = distance(vec3(global_unit_position), vec3(world_unit_shape - cell_shape * (world_shape % 2)) / 2.0);
    float normalized_radius = radius / sphere_radius;
    uint layer = clamp(uint(5.0 * normalized_radius), 0u, 4u) + 1u;

    Cell cell;
    cell.filled_units = 1u;

    Unit unit;
    if (global_unit_position % 4u == uvec3(0)) {
        unit.substance = layer;
        unit.quantity = uint(1000.0 * (sphere_radius - radius) / radius);
    }

    imageStore(u_world_unit_write.handles[chunk_index], global_unit_position, pack_unit(unit));
    // todo: Перестроить шейдер на то, чтобы он создавал ячейки
    imageStore(u_world_cell_write.handles[chunk_index], global_cell_position, pack_cell(cell));
}
