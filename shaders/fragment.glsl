#version 460

uniform vec2 u_window_size;
uniform float u_fov_scale;
uniform float u_near;
uniform float u_far;
uniform ivec3 u_world_shape;
uniform vec4 u_background;

uniform vec3 u_view_position;
uniform vec3 u_view_forward;
uniform vec3 u_view_right;
uniform vec3 u_view_up;
uniform float u_zoom;
uniform sampler3D u_colors;

out vec4 f_color;

// todo: Добавить преломление
// todo: Передавать текстуру с данными о материале (bool, bool, bool, bool)
//  (наличие чего-либо в вокселе, непрозрачность, зеркальность, четвертая характеристика)
// todo: Уйти от "стеклянных" вокселей. Не просто добавлять цвет лучу по прохождении границы вокселя,
//  а добавлять цвет по количеству пройденного расстояния внутри вокселя.
void main() {
    ivec3 world_min = ivec3(0);
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
    vec3 distance_to_maxes = (world_max + 1 - biased_view_position) * ray_backward;
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
            || any(greaterThan(voxel_position, world_max))) {
                break;
            }

            vec4 voxel_color = texelFetch(u_colors, ivec3(voxel_position - world_min), 0);

            if (voxel_color.a > 0.01) {
                float alpha = voxel_color.a * (1.0 - ray_color.a);
                ray_color += vec4(voxel_color.rgb * alpha, alpha);
                if (ray_color.a >= 0.99) break;
            }

            vec3 mask = step(next_boundary.xyz, next_boundary.yzx) * step(next_boundary.xyz, next_boundary.zxy);
            next_boundary += mask * step_size;
            voxel_position += mask * step_forward;
        }
    }

    f_color = vec4(ray_color.rgb + (1.0 - ray_color.a) * u_background.rgb, 1.0);
}
