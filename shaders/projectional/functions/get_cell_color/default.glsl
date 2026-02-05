uniform float u_optical_density_scale;


struct SubstanceOptics {
    vec3 color;
    float absorption;
};


SubstanceOptics unpack_substance_optics (uvec2 packed_optics) {
    SubstanceOptics optics;

    optics.color.r = float(bitfieldExtract(packed_optics.r, 0, 8)) / normal_8;
    optics.color.g = float(bitfieldExtract(packed_optics.r, 8, 8)) / normal_8;
    optics.color.b = float(bitfieldExtract(packed_optics.r, 16, 8)) / normal_8;

    optics.absorption = uintBitsToFloat(packed_optics.g);

    return optics;
}


layout(std430, binding = 20) readonly restrict buffer SubstanceOpticsBuffer {
    uvec2 data[];
} u_substance_optics;

layout(std430, binding = 0) readonly restrict buffer World {
    usampler3D handles[];
} u_world;


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
        SubstanceOptics optics = unpack_substance_optics(u_substance_optics.data[unit.substance_id]);

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
