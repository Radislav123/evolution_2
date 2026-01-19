uniform uint u_connected_texture_count;
uniform float u_optical_density_scale;

uniform sampler1D u_colors;
uniform sampler1D u_absorption;

layout(std430, binding = 0) readonly restrict buffer Substances {
    usampler3D handles[];
} u_substances[2];
layout(std430, binding = 2) readonly restrict buffer Quantities {
    usampler3D handles[];
} u_quantities[2];


vec4 get_voxel_color(ivec3 position) {
    vec3 rgb_squared = vec3(0.0);
    float optical_depth = 0.0;
    vec3 rgb = vec3(0.0);
    float opacity = 0.0;

    for (uint texture_index = 0u; texture_index < u_connected_texture_count; texture_index++) {
        uvec4 substances_4 = texelFetch(u_substances[0].handles[texture_index], position, 0);
        uvec4 quantities_4 = texelFetch(u_quantities[0].handles[texture_index], position, 0);

        for (uint channel_index = 0u; channel_index < 4u; channel_index++) {
            uint substance_id = substances_4[channel_index];
            uint quantity = quantities_4[channel_index];
            if (substance_id == 0U || quantity == 0u) continue;

            float absorption_rate = texelFetch(u_absorption, int(substance_id), 0).r;
            vec3 substance_rgb_val = texelFetch(u_colors, int(substance_id), 0).rgb;

            float substance_optical_depth = absorption_rate * float(quantity);
            optical_depth += substance_optical_depth;
            rgb_squared += substance_rgb_val * substance_rgb_val * substance_optical_depth;
        }
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
