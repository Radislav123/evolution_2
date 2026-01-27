struct Cell {
    uint filled_units;
};


Cell unpack_cell(uvec4 packed_cell) {
    Cell cell;

    cell.filled_units = bitfieldExtract(packed_cell.r, 0, 6);

    return cell;
}
