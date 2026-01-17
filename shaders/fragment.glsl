#version 460
#extension GL_ARB_bindless_texture : require

const int max_cell_substance_count = 32;

uniform vec2 u_window_size;
uniform float u_fov_scale;
uniform float u_near;
uniform float u_far;
uniform ivec3 u_world_shape;
uniform int u_connected_texture_count;

uniform vec4 u_background;
uniform float u_optical_density_scale;

uniform bool u_test_color_cube;
uniform vec4 u_test_color_cube_start;
uniform vec4 u_test_color_cube_end;

uniform vec3 u_view_position;
uniform vec3 u_view_forward;
uniform vec3 u_view_right;
uniform vec3 u_view_up;
uniform float u_zoom;

uniform sampler1D u_colors;
uniform sampler1D u_absorption;

layout(std430, binding = 0) buffer Substances {
    usampler3D u_substances[];
};
layout(std430, binding = 1) buffer Quantities {
    usampler3D u_quantities[];
};

out vec4 f_color;


vec4 get_voxel_color_test(ivec3 position) {
    vec4 start = u_test_color_cube_start;
    vec4 end = u_test_color_cube_end;
    vec3 rate = vec3(position) / vec3(u_world_shape);

    vec3 rgb = start.rgb * rate + end.rgb * (1 - rate);
    float alpha = (start.a + end.a) / 2;

    return vec4(rgb, alpha);
}


// performance: предрасчитывать цвет вокселя в compute shader
vec4 get_voxel_color(ivec3 position) {
    vec3 rgb_squared = vec3(0.0);
    float optical_depth = 0.0;
    vec3 rgb = vec3(0.0);
    float opacity = 0.0;

    for (int texture_index = 0; texture_index < u_connected_texture_count; texture_index++) {
        uvec4 substances_4 = texelFetch(u_substances[texture_index], position, 0);
        uvec4 quantities_4 = texelFetch(u_quantities[texture_index], position, 0);

        for (int channel_index = 0; channel_index < 4; channel_index++) {
            uint substance_id = substances_4[channel_index];
            uint quantity = quantities_4[channel_index];

            if (substance_id == 0u || quantity == 0u) continue;

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


// performance: После разбиения на чанки, можно помечать чанки, в которых ничего не нужно рисовать?
// todo: Добавить преломление
// todo: Добавить отражение
// todo: Уйти от "стеклянных" вокселей. Не просто добавлять цвет лучу по прохождении границы вокселя,
//  а добавлять цвет по количеству пройденного расстояния внутри вокселя.
void main() {
    ivec3 world_min = ivec3(0.0);
    ivec3 world_max = u_world_shape;

    // Координаты пикселя на мониторе, со смещением цетнра координат в центр экрана
    vec2 pixel_position = (gl_FragCoord.xy - 0.5 * u_window_size) / (u_window_size.y * 0.5);

    // Направление луча в локальных координатах камеры
    vec3 ray_forward_local = normalize(vec3(
    pixel_position.x * u_fov_scale / u_zoom,
    pixel_position.y * u_fov_scale / u_zoom,
    1.0
    ));

    // Перевод в мировые координаты
    vec3 ray_forward = normalize(
    u_view_right * ray_forward_local.x +
    u_view_up * ray_forward_local.y +
    u_view_forward * ray_forward_local.z
    );

    // Смещение отображения мира так, чтобы центр воксел (0, 0, 0) был в позиции (0, 0, 0)
    vec3 biased_view_position = u_view_position + vec3(0.5);

    // Нужно для ускорения вычислений, заменяет деление на умножение
    vec3 ray_backward = 1.0 / (ray_forward + vec3(1e-9));
    vec3 distance_to_mins = (world_min - biased_view_position) * ray_backward;
    vec3 distance_to_maxes = (world_max - biased_view_position) * ray_backward;
    vec3 near_bounds = min(distance_to_mins, distance_to_maxes);
    vec3 far_bounds = max(distance_to_mins, distance_to_maxes);

    float entry_distance = max(max(max(near_bounds.x, near_bounds.y), near_bounds.z), u_near);
    float exit_distance = min(min(min(far_bounds.x, far_bounds.y), far_bounds.z), u_far);

    vec4 ray_color = vec4(0.0);

    if (exit_distance > max(entry_distance, 0.0)) {
        // Расстояние до границы мира, или 0, если камера внутри мира
        float ray_start_offset = max(entry_distance, 0.0) + 0.001;
        vec3 ray_start = biased_view_position + ray_forward * ray_start_offset;

        // Позиция вокселя, внутри которого сейчас находится луч
        vec3 voxel_position = floor(ray_start);
        vec3 step_forward = sign(ray_forward);
        vec3 step_size = abs(ray_backward);

        vec3 next_boundary = (voxel_position - ray_start + max(step_forward, 0.0)) * ray_backward;

        int max_iterations = u_world_shape.x + u_world_shape.y + u_world_shape.z;
        for (int i = 0; i < max_iterations; i++) {
            // Проверка границ
            if (any(lessThan(voxel_position, world_min))
            || any(greaterThanEqual(voxel_position, world_max))) break;

            vec4 voxel_color = u_test_color_cube ?
            get_voxel_color_test(ivec3(voxel_position)) :
            get_voxel_color(ivec3(voxel_position));

            if (voxel_color.a > 0.01) {
                float alpha = voxel_color.a * (1.0 - ray_color.a);
                ray_color += vec4(voxel_color.rgb * alpha, alpha);
                if (ray_color.a >= 0.99) break;
            }

            vec3 mask = step(next_boundary.xyz, next_boundary.yzx) * step(next_boundary.xyz, next_boundary.zxy);
            if (mask.x > 0.0) mask.yz = vec2(0.0);
            else if (mask.y > 0.0) mask.z = 0.0;
            next_boundary += mask * step_size;
            voxel_position += mask * step_forward;
        }
    }

    f_color = vec4(ray_color.rgb + (1.0 - ray_color.a) * u_background.rgb, 1.0);
}
