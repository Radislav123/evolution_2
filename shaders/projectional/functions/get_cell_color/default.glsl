uniform float u_optical_density_scale;


vec4 get_cell_color(ivec3 cell_position) {
    Cell cell = read_cell(cell_position);
    vec3 rgb_squared = vec3(0.0);
    vec3 rgb = vec3(0.0);
    float optical_depth = 0.0;
    float opacity = 0.0;

    for (int unit_index = 0; unit_index < cell.filled_units; unit_index++) {
        Unit unit = read_unit(cell_position, unit_index);
        SubstanceOptics optics = read_substance_optics(unit.substance_id);

        float substance_optical_depth = optics.absorption * float(unit.quantity);
        rgb_squared += optics.color * optics.color * substance_optical_depth;
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
