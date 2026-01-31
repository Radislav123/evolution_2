uniform float u_optical_density_scale;

uniform sampler1D u_colors;
uniform sampler1D u_absorption;

layout(std430, binding = 0) readonly restrict buffer World {
    usampler3D handles[];
} u_world;


struct Cell {
    uint filled_units;
};


struct Unit {
    uint substance;
    uint quantity;
};


// todo: Вынести их к основным версиям?
// Здесь специально упрощенные версии распаковки
Cell unpack_cell(uvec4 packed_cell) {
    Cell cell;

    cell.filled_units = bitfieldExtract(packed_cell.r, 0, 6);

    return cell;
}


Unit unpack_unit(uvec4 packed_unit) {
    Unit unit;

    unit.substance = bitfieldExtract(packed_unit.r, 0, 16);
    unit.quantity = bitfieldExtract(packed_unit.r, 16, 16);

    return unit;
}


vec4 get_cell_color(in ivec3 cell_position) {
    vec3 rgb_squared = vec3(0.0);
    float optical_depth = 0.0;
    vec3 rgb = vec3(0.0);
    float opacity = 0.0;
    uint chunk_index = 0;

    Cell cell = unpack_cell(texelFetch(u_world.handles[chunk_index], cell_position, 2));
    for (int unit_index = 0; unit_index < cell.filled_units; unit_index++) {
        // Позиция юнита в ячейке
        ivec3 local_position = ivec3(unit_index & 3, (unit_index >> 2) & 3, unit_index >> 4);
        Unit unit = unpack_unit(texelFetch(u_world.handles[chunk_index], cell_position * cell_shape + local_position, 0));

        vec3 substance_rgb_val = texelFetch(u_colors, int(unit.substance), 0).rgb;
        float absorption_rate = texelFetch(u_absorption, int(unit.substance), 0).r;

        float substance_optical_depth = absorption_rate * float(unit.quantity);
        rgb_squared += substance_rgb_val * substance_rgb_val * substance_optical_depth;
        optical_depth += substance_optical_depth;
    }

    if (optical_depth > 0.0) {
        rgb = sqrt(rgb_squared / optical_depth);

        float absorption = optical_depth * u_optical_density_scale;
        // Текущий вариант должен быть быстрее, чем с exp(), но пока что этого не видно
        // opacity = 1.0 - exp(-absorption);
        opacity = absorption / (1.0 + absorption);
    }

    return vec4(rgb, opacity);
}
