struct Cell {
    uint filled_units;
    uint request_count[6];
};


Cell unpack_cell(uvec4 packed_cell) {
    Cell cell;

    cell.filled_units = bitfieldExtract(packed_cell.r, 0, 6);
    cell.request_count[0] = bitfieldExtract(packed_cell.r, 6, 6);
    cell.request_count[1] = bitfieldExtract(packed_cell.r, 12, 6);

    return cell;
}


uvec4 pack_cell(Cell cell) {
    uvec4 packed_cell = uvec4(0);

    // Так как юнитов 64, значение не может быть больше 6 битов, и применять маску не нужно
    packed_cell.r = cell.filled_units
    | (cell.request_count[0] << 6)
    | (cell.request_count[1] << 12);

    return packed_cell;
}
