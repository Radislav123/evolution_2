const ivec3 world_shape = world_shape_placeholder;
const ivec3 world_unit_shape = world_unit_shape_placeholder;

const ivec3 cell_shape = cell_shape_placeholder;
const ivec3 block_shape = block_shape_placeholder;
const int cell_size = cell_shape.x * cell_shape.y * cell_shape.z;

const ivec3 world_min = ivec3(0);
const ivec3 world_max = world_shape - 1;

const ivec3 request_min_momentum = request_min_momentum_placeholder;
