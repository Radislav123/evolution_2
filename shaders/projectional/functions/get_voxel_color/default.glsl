uniform float u_optical_density_scale;

uniform sampler1D u_colors;
uniform sampler1D u_absorption;

layout(std430, binding = 0) readonly restrict buffer World {
    usampler3D handles[];
} u_world[2];


struct Unit {
    uint substance;
    uint quantity;
};

Unit unpack_unit(uvec4 packed_unit) {
    Unit unit;

    unit.substance = bitfieldExtract(packed_unit.r, 0, 15);
    unit.quantity = bitfieldExtract(packed_unit.r, 15, 15);

    return unit;
}


// todo: Выделить функцию для вичисления цвета вокселя, а эту очистиить от всего лишнего
vec4 get_unit_color(ivec3 position) {
    vec3 rgb_squared = vec3(0.0);
    float optical_depth = 0.0;
    vec3 rgb = vec3(0.0);
    float opacity = 0.0;
    uint chunk_index = 0;

    // u_world[0] - текстура для чтения
    // u_world[1] - текстура для записи, которая в данном шейдере не используется
    Unit unit = unpack_unit(texelFetch(u_world[0].handles[chunk_index], position, 0));

    float absorption_rate = texelFetch(u_absorption, int(unit.substance), 0).r;
    vec3 substance_rgb_val = texelFetch(u_colors, int(unit.substance), 0).rgb;

    float substance_optical_depth = absorption_rate * float(unit.quantity);
    optical_depth += substance_optical_depth;
    rgb_squared += substance_rgb_val * substance_rgb_val * substance_optical_depth;

    if (optical_depth > 0.0) {
        rgb = sqrt(rgb_squared / optical_depth);

        float absorption = optical_depth * u_optical_density_scale;
        // Текущий вариант должен быть быстрее, чем с exp(), но пока что этого не видно
        // opacity = 1.0 - exp(-absorption);
        opacity = absorption / (1.0 + absorption);
    }

    return vec4(rgb, opacity);
}
