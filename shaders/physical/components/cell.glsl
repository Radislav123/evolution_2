struct Cell {
    uint filled_units;
};


Cell unpack_cell(uvec4 packed_cell) {
    Cell cell;

    cell.filled_units = bitfieldExtract(packed_cell.r, 0, 6);

    return cell;
}


uvec4 pack_cell(Cell cell) {
    uvec4 packed_cell = uvec4(0);

    packed_cell.r = cell.filled_units;

    return packed_cell;
}
