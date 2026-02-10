#version 460
#extension GL_ARB_bindless_texture : require


#include physical_constants
#include packing_constants

#include unit_component
#include plan_component
#include cell_component
#include substance_component



layout(local_size_x = cell_group_shape.x, local_size_y = cell_group_shape.y, local_size_z = cell_group_shape.z) in;
shared Cell cell_cache[cell_cache_shape.x][cell_cache_shape.y][cell_cache_shape.z];


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


void main() {
    ivec3 group_position = ivec3(gl_WorkGroupID);
    ivec3 global_cell_position = ivec3(gl_GlobalInvocationID);
    int gloup_cell_index = int(gl_LocalInvocationIndex);
    int chunk_index = 0;

    for (int cell_index = gloup_cell_index; cell_index < cell_cache_size; cell_index += cell_group_size) {
        ivec3 cache_cell_position = ivec3(
        cell_index % cell_cache_shape.x,
        (cell_index % (cell_cache_shape.x * cell_cache_shape.y)) / cell_cache_shape.x,
        cell_index / (cell_cache_shape.x * cell_cache_shape.y)
        );
        ivec3 read_position = (cache_cell_position + ivec3(group_position * cell_group_shape) - 1 + world_shape) % world_shape;

        cell_cache[cache_cell_position.x][cache_cell_position.y][cache_cell_position.z] = read_cell(read_position);
    }

    memoryBarrierShared();
    barrier();

    // Сдвиг на + 1 так как в кэш записывается еще слой поверх группы
    ivec3 cache_cell_position = ivec3(gl_LocalInvocationID) + 1;
    Cell cell = cell_cache[cache_cell_position.x][cache_cell_position.y][cache_cell_position.z];
    Plan plan = read_plan(global_cell_position);

    for (int local_unit_index = 0; local_unit_index < cell.filled_units; local_unit_index++) {
        int plan_section = local_unit_index / 32;
        int plan_section_index = local_unit_index % 32;

        ivec3 global_unit_position = unit_index_to_position(global_cell_position, local_unit_index);
        Unit unit = read_unit(global_unit_position);
        Substance substance = read_substance(unit.substance_id);

        unit.momentum += global_cell_position.x > 0 ? u_gravity_vector * unit.quantity * u_world_update_period : ivec3(0.0);
        int momentum_d = unit.momentum[u_world_age % 3];
        if (abs(momentum_d) >= substance.mass) {
            plan.presence[plan_section] = bitfieldInsert(plan.presence[plan_section], 1, plan_section_index, 1);
            plan.direction[plan_section] = bitfieldInsert(plan.direction[plan_section], sign(momentum_d), plan_section_index, 1);
        }

        write_unit(global_unit_position, unit);
    }

    write_plan(global_cell_position, plan);
    write_cell(global_cell_position, cell);
}
