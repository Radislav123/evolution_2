#version 460
#extension GL_ARB_bindless_texture : require


#include physical_constants
#include packing_constants
#include common_constants

#include cell_component
#include unit_component
#include substance_component


layout(local_size_x = cell_group_shape.x, local_size_y = cell_group_shape.y, local_size_z = cell_group_shape.z) in;


layout(std430, binding = 1) writeonly restrict buffer WorldCellWrite {
    uimage3D handles[];
} u_world_cell_write;
layout(std430, binding = 2) writeonly restrict buffer WorldBlockWrite {
    uimage3D handles[];
} u_world_block_write;
layout(std430, binding = 3) writeonly restrict buffer WorldUnitWrite {
    uimage3D handles[];
} u_world_unit_write;

layout(std430, binding = 10) readonly restrict buffer SubstanceBuffer {
    Substance data[];
} u_substance_buffer;


void main() {
    ivec3 global_cell_position = ivec3(gl_GlobalInvocationID);
    int substance_count = u_substance_buffer.data.length();
    int chunk_index = 0;

    float sphere_radius = float(min(world_shape.x, min(world_shape.y, world_shape.z))) / 2.0;
    float radius = distance(vec3(global_cell_position), vec3(world_shape) / 2.0);
    float normalized_radius = radius / sphere_radius;
    int layer = clamp(int(float(substance_count - 1) * normalized_radius), 0, substance_count - 1) + 1;

    Cell cell = new_cell();
    Unit unit = new_unit();

    ivec3 global_unit_position = global_cell_position * cell_shape;
    unit.quantity = int(300.0 * (sphere_radius - radius) / radius);
    unit.substance_id = unit.quantity > 0 ? layer : 0;
    cell.filled_units = unit.quantity > 0 ? 1 : 0;

    Substance substance = u_substance_buffer.data[unit.substance_id];

    imageStore(u_world_cell_write.handles[chunk_index], global_cell_position, pack_cell(cell));
    imageStore(u_world_unit_write.handles[chunk_index], global_unit_position, pack_unit(unit));
}
