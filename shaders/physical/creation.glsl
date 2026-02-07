#version 460
#extension GL_ARB_bindless_texture : require


#include physical_constants
#include packing_constants
#include common_constants

#include cell_component
#include unit_component
#include substance_component


layout(local_size_x = cell_group_shape.x, local_size_y = cell_group_shape.y, local_size_z = cell_group_shape.z) in;


void main() {
    ivec3 cell_position = ivec3(gl_GlobalInvocationID);
    int substance_count = u_substance_buffer.data.length();

    float sphere_radius = float(min(world_shape.x, min(world_shape.y, world_shape.z))) / 2.0;
    float radius = distance(vec3(cell_position), vec3(world_shape) / 2.0);
    float normalized_radius = radius / sphere_radius;
    int layer = clamp(int(float(substance_count - 1) * normalized_radius), 0, substance_count - 1) + 1;

    Cell cell = new_cell();
    Unit unit = new_unit();

    unit.quantity = int(300.0 * (sphere_radius - radius) / radius);
    unit.substance_id = unit.quantity > 0 ? layer : 0;
    cell.filled_units = unit.quantity > 0 ? 1 : 0;

    Substance substance = read_substance(unit.substance_id);

    write_unit(cell_position, 0, unit);
    write_cell(cell_position, cell);
}
