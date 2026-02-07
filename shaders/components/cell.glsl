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


layout(std430, binding = 1) readonly restrict buffer CellReadBuffer {
    uvec4 data[];
} u_cell_buffer_read;
layout(std430, binding = 3) writeonly restrict buffer CellWriteBuffer {
    uvec4 data[];
} u_cell_buffer_write;


//int cell_position_to_index(ivec3 position) {
//    // performance: Перейти на кривую Мортона + lookup table
//    return position.x + world_shape.x * position.y + world_shape.x * world_shape.y * position.z;
//}

// todo: Связать 8u с размером вычислительного блока
// todo: Переписать
int cell_position_to_index(ivec3 position) {
    uvec3 u_position = uvec3(position);
    uvec3 u_group_position = u_position / 8u;
    uvec3 u_local_position = u_position % 8u;

    uint group_index = u_group_position.x +
    u_group_position.y * uint(world_group_shape.x) +
    u_group_position.z * uint(world_group_shape.x * world_group_shape.y);

    const uint lut[8] = uint[](0u, 1u, 8u, 9u, 64u, 65u, 72u, 73u);
    uint local_index = lut[u_local_position.x] | (lut[u_local_position.y] << 1) | (lut[u_local_position.z] << 2);
    return int((group_index << 9) | local_index);
}


Cell read_cell_base(int index) {
    uvec4 packed_cell = u_cell_buffer_read.data[index];
    Cell cell;

    cell.filled_units = int(bitfieldExtract(packed_cell.r, 0, 6));
    cell.plan_count_0 = int(bitfieldExtract(packed_cell.r, 6, 6));
    cell.plan_count_1 = int(bitfieldExtract(packed_cell.r, 12, 6));

    return cell;
}

Cell read_cell(int index) {
    return read_cell_base(index);
}

Cell read_cell(ivec3 position) {
    return read_cell_base(cell_position_to_index(position));
}


void write_cell_base(int index, Cell cell) {
    uvec4 packed_cell = uvec4(0);

    packed_cell.r = uint(cell.filled_units);
    packed_cell.r = bitfieldInsert(packed_cell.r, uint(cell.plan_count_0), 6, 6);
    packed_cell.r = bitfieldInsert(packed_cell.r, uint(cell.plan_count_1), 12, 6);

    u_cell_buffer_write.data[index] = packed_cell;
}

void write_cell(int index, Cell cell) {
    write_cell_base(index, cell);
}

void write_cell(ivec3 position, Cell cell) {
    write_cell_base(cell_position_to_index(position), cell);
}
