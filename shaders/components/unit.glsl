layout(std430, binding = 0) readonly restrict buffer ReadUnit {
    usampler3D handles[];
} u_read_unit;
layout(std430, binding = 5) writeonly restrict buffer WriteUnit {
    uimage3D handles[];
} u_write_unit;


struct Unit {
    int substance_id;// 14 - [-8192; 8191]
    int quantity;// 10 - [0; 1023]
// Импульс всего юнита
    ivec3 momentum;// 16 - [-32768; 32767]
// Заявка всегда 1/6 от импульса и количество, поэтому ее можно не хранить, можно хранить только признак ее наличия
    bool plan;
};


Unit new_unit() {
    return Unit(0, 0, ivec3(0u), false);
}


ivec3 unit_index_to_position(ivec3 cell_position, int local_index) {
    ivec3 local_position = ivec3(
    local_index % cell_shape.x,
    (local_index / cell_shape.x) % cell_shape.y,
    local_index / (cell_shape.x * cell_shape.y)
    );
    return cell_position * cell_shape + local_position;
}


// r - [0; 23]
// g - [0; 29]
// b - [0; 17]
// a - []
Unit read_unit_base(ivec3 position) {
    int chunk_index = 0;
    uvec4 packed_unit = texelFetch(u_read_unit.handles[chunk_index], position, 0);
    Unit unit;

    unit.substance_id = int(bitfieldExtract(packed_unit.r, 0, 14));
    unit.quantity = int(bitfieldExtract(packed_unit.r, 14, 10));

    unit.momentum.x = int(bitfieldExtract(packed_unit.g, 0, 10) | (bitfieldExtract(packed_unit.b, 0, 6) << 10));
    unit.momentum.y = int(bitfieldExtract(packed_unit.g, 10, 10) | (bitfieldExtract(packed_unit.b, 6, 6) << 10));
    unit.momentum.z = int(bitfieldExtract(packed_unit.g, 20, 10) | (bitfieldExtract(packed_unit.b, 12, 6) << 10));
    unit.momentum -= zero_offset_16;

    return unit;
}

Unit read_unit(ivec3 global_position) {
    return read_unit_base(global_position);
}

Unit read_unit(ivec3 cell_position, int local_index) {
    return read_unit_base(unit_index_to_position(cell_position, local_index));
}


// todo: Внедрить проверку на переполнение упаковываемых величин, которую можно будет убирать до компиляции, в случае необходимости (макрос для проверки переполнения, который можно отключать #define) 
void write_unit_base(ivec3 position, Unit unit) {
    int chunk_index = 0;
    uvec4 packed_unit = uvec4(0u);

    packed_unit.r = uint(unit.substance_id);
    packed_unit.r = bitfieldInsert(packed_unit.r, uint(unit.quantity), 14, 10);

    uvec3 momentum = uvec3(unit.momentum + zero_offset_16);
    packed_unit.g = momentum.x;
    packed_unit.g = bitfieldInsert(packed_unit.g, momentum.y, 10, 10);
    packed_unit.g = bitfieldInsert(packed_unit.g, momentum.z, 20, 10);
    packed_unit.b = momentum.x >> 10;
    packed_unit.b = bitfieldInsert(packed_unit.b, momentum.y >> 10, 6, 6);
    packed_unit.b = bitfieldInsert(packed_unit.b, momentum.z >> 10, 12, 6);

    imageStore(u_write_unit.handles[chunk_index], position, packed_unit);
}

void write_unit(ivec3 global_position, Unit unit) {
    write_unit_base(global_position, unit);
}

void write_unit(ivec3 cell_position, int local_index, Unit unit) {
    write_unit_base(unit_index_to_position(cell_position, local_index), unit);
}
