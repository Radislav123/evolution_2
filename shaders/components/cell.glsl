layout(std430, binding = 1) readonly restrict buffer ReadCell {
    usampler3D handles[];
} u_read_cell;
layout(std430, binding = 6) writeonly restrict buffer WriteCell {
    uimage3D handles[];
} u_write_cell;


struct Cell {
    int filled_units;
// Ось соседа == world_age % 3
// Количество заявок в соседа 0
    int plan_count_0;
// Количество заявок в соседа 1
    int plan_count_1;
};


Cell new_cell() {
    return Cell(0, 0, 0);
}


int cell_position_to_index(ivec3 position) {
    return position.x + world_shape.x * position.y + world_shape.x * world_shape.y * position.z;
}


Cell read_cell(ivec3 position) {
    int chunk_index = 0;
    uvec4 packed_cell = texelFetch(u_read_cell.handles[chunk_index], position, 0);
    Cell cell;

    cell.filled_units = int(bitfieldExtract(packed_cell.r, 0, 6));
    cell.plan_count_0 = int(bitfieldExtract(packed_cell.r, 6, 6));
    cell.plan_count_1 = int(bitfieldExtract(packed_cell.r, 12, 6));

    return cell;
}


void write_cell(ivec3 position, Cell cell) {
    int chunk_index = 0;
    uvec4 packed_cell = uvec4(0);

    packed_cell.r = uint(cell.filled_units);
    packed_cell.r = bitfieldInsert(packed_cell.r, uint(cell.plan_count_0), 6, 6);
    packed_cell.r = bitfieldInsert(packed_cell.r, uint(cell.plan_count_1), 12, 6);

    imageStore(u_write_cell.handles[chunk_index], position, packed_cell);
}
