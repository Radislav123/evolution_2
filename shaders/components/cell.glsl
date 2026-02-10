layout(std430, binding = 2) readonly restrict buffer ReadCell {
    usampler3D handles[];
} u_read_cell;
layout(std430, binding = 7) writeonly restrict buffer WriteCell {
    uimage3D handles[];
} u_write_cell;


const ivec3 cell_offsets[6] = ivec3[6](
ivec3(-1, 0, 0),
ivec3(1, 0, 0),
ivec3(0, -1, 0),
ivec3(0, 1, 0),
ivec3(0, 0, -1),
ivec3(0, 0, 1)
);


struct Cell {
    int filled_units;
};


Cell new_cell() {
    return Cell(0);
}


int cell_position_to_index(ivec3 position) {
    return position.x + world_shape.x * position.y + world_shape.x * world_shape.y * position.z;
}


// r - [0; 29]
// g - []
// b - [0; 31]
// a - [0; 31]
Cell read_cell(ivec3 position) {
    int chunk_index = 0;
    uvec4 packed_cell = texelFetch(u_read_cell.handles[chunk_index], position, 0);
    Cell cell;

    cell.filled_units = int(bitfieldExtract(packed_cell.r, 0, 6));

    return cell;
}


void write_cell(ivec3 position, Cell cell) {
    int chunk_index = 0;
    uvec4 packed_cell = uvec4(0u);

    packed_cell.r = uint(cell.filled_units);

    imageStore(u_write_cell.handles[chunk_index], position, packed_cell);
}
