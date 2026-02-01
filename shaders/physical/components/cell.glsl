struct Cell {
    int filled_units;
    int plan_count[2];
};


Cell new_cell() {
    return Cell(0, int[2](0, 0));
}


Cell unpack_cell(uvec4 packed_cell) {
    Cell cell;

    cell.filled_units = int(bitfieldExtract(packed_cell.r, 0, 6));
    cell.plan_count[0] = int(bitfieldExtract(packed_cell.r, 6, 6));
    cell.plan_count[1] = int(bitfieldExtract(packed_cell.r, 12, 6));

    return cell;
}


uvec4 pack_cell(Cell cell) {
    uvec4 packed_cell = uvec4(0);

    // Так как юнитов 64, значение не может быть больше 6 битов, и применять маску не нужно
    packed_cell.r = uint(cell.filled_units)
    | (uint(cell.plan_count[0]) << 6)
    | (uint(cell.plan_count[1]) << 12);

    return packed_cell;
}
