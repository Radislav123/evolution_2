#version 460
#extension GL_ARB_bindless_texture : require


#include physical_constants
#include packing_constants

#include cell_component
#include unit_component
#include substance_optics_component


// Переменные, которые почти не меняются или меняются редко
uniform vec2 u_window_size;
uniform float u_fov_scale;
uniform float u_near;
uniform float u_far;

uniform vec4 u_background;

// Переменные, которые могу меняться каждый кадр
// Порядок и дополнения до 16 байт должны совпадать с тем, что обхявлено в python-коде
layout(std140, binding = 3) uniform CameraBuffer {
    vec3 u_view_position;
    int u_padding_0;
    vec3 u_view_forward;
    int u_padding_1;
    vec3 u_view_right;
    int u_padding_2;
    vec3 u_view_up;
    float u_zoom;
};


out vec4 f_color;


#include color_function


// todo: Добавить преломление
// todo: Добавить отражение (если отражение частичное, то дублировать луч)
void main() {
    // Координаты пикселя на мониторе, со смещением цетнра координат в центр экрана
    vec2 pixel_position_normalized = (gl_FragCoord.xy - 0.5 * u_window_size) / (u_window_size.y * 0.5);

    // Направление луча в локальных координатах камеры
    vec3 ray_forward_local = normalize(vec3(
    pixel_position_normalized.x * u_fov_scale / u_zoom,
    pixel_position_normalized.y * u_fov_scale / u_zoom,
    1.0
    ));

    // Перевод в мировые координаты
    vec3 ray_forward = normalize(
    u_view_right * ray_forward_local.x +
    u_view_up * ray_forward_local.y +
    u_view_forward * ray_forward_local.z
    );

    // Смещение отображения мира так, чтобы центр ячейки (0, 0, 0) был в позиции (0, 0, 0)
    vec3 biased_view_position = u_view_position + vec3(0.5);

    // Нужно для ускорения вычислений, заменяет деление на умножение
    vec3 ray_backward = 1.0 / (ray_forward + vec3(1e-10));
    vec3 distance_to_mins = (world_min - biased_view_position) * ray_backward;
    vec3 distance_to_maxes = (world_max - biased_view_position + 1) * ray_backward;
    vec3 near_bounds = min(distance_to_mins, distance_to_maxes);
    vec3 far_bounds = max(distance_to_mins, distance_to_maxes);

    float entry_distance = max(max(max(near_bounds.x, near_bounds.y), near_bounds.z), u_near);
    float exit_distance = min(min(min(far_bounds.x, far_bounds.y), far_bounds.z), u_far);
    vec4 ray_color = vec4(0.0, 0.0, 0.0, 0.0);

    if (exit_distance > max(entry_distance, 0.0)) {
        // Расстояние до границы мира, или 0, если камера внутри мира
        float ray_start_offset = max(entry_distance, 0.0) + 1e-4;
        vec3 ray_start = biased_view_position + ray_forward * ray_start_offset;

        // Позиция ячейки, внутри которой находится луч
        vec3 cell_position = floor(ray_start);
        vec3 step_forward = sign(ray_forward);
        vec3 step_size = abs(ray_backward);

        float ray_length = ray_start_offset;
        vec3 next_boundary = (cell_position - ray_start + max(step_forward, 0.0)) * ray_backward;
        int max_iterations = world_shape.x + world_shape.y + world_shape.z;
        for (int iteration = 0; iteration < max_iterations; iteration++) {
            // Проверка границ
            if (any(lessThan(cell_position, world_min)) || any(greaterThan(cell_position, world_max))) break;

            float future_ray_length = min(min(next_boundary.x, next_boundary.y), next_boundary.z);
            float distance = future_ray_length - ray_length;
            vec4 cell_color = get_cell_color(ivec3(cell_position), distance);

            if (cell_color.a > 0.01) {
                float alpha = cell_color.a * (1.0 - ray_color.a);
                ray_color += vec4(cell_color.rgb * alpha, alpha);
                if (ray_color.a >= 0.99) break;
            }

            vec3 mask = step(next_boundary.xyz, next_boundary.yzx) * step(next_boundary.xyz, next_boundary.zxy);
            if (mask.x > 0.0) mask.yz = vec2(0.0);
            else if (mask.y > 0.0) mask.z = 0.0;
            cell_position += mask * step_forward;
            next_boundary += mask * step_size;
            ray_length = future_ray_length;
        }
    }

    f_color = vec4(ray_color.rgb + (1.0 - ray_color.a) * u_background.rgb, 1.0);
}
