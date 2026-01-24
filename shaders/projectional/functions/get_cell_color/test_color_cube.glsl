uniform vec4 u_test_color_cube_start;
uniform vec4 u_test_color_cube_end;


vec4 get_cell_color(ivec3 position) {
    vec4 start = u_test_color_cube_start;
    vec4 end = u_test_color_cube_end;
    vec3 rate = vec3(position) / vec3(u_world_shape);

    vec3 rgb = start.rgb * rate + end.rgb * (1 - rate);
    float alpha = (start.a + end.a) / 2;

    return vec4(rgb, alpha);
}
