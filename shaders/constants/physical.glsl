const ivec3 world_shape = world_shape_placeholder;
const ivec3 cell_shape = cell_shape_placeholder;
const int cell_size = cell_size_placeholder;

const ivec3 world_group_shape = world_group_shape_placeholder;
const ivec3 cell_group_shape = cell_group_shape_placeholder;
const ivec3 cell_cache_shape = cell_group_shape + 2;
const int cell_group_size = cell_group_shape.x * cell_group_shape.y * cell_group_shape.z;
const int cell_cache_size = cell_cache_shape.x * cell_cache_shape.y * cell_cache_shape.z;

const ivec3 world_min = ivec3(0);
const ivec3 world_max = world_shape - 1;
