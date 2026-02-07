struct Plan {
    int quantity;// 8 - [0; 255]
    int momentum_d;// 14 - [-8192; 8191]
};


struct Unit {
    int substance_id;// 14 - [-8192; 8191]
    int quantity;// 10 - [0; 1023]
// Импульс всего юнита
    ivec3 momentum;// 16 - [-32768; 32767]
    Plan plan;
};


Unit new_unit() {
    return Unit(0, 0, ivec3(0), Plan(0, 0));
}


layout(std430, binding = 0) readonly restrict buffer UnitReadBuffer {
    uvec4 data[];
} u_unit_buffer_read;
layout(std430, binding = 2) writeonly restrict buffer UnitWriteBuffer {
    uvec4 data[];
} u_unit_buffer_write;


int unit_position_to_index(ivec3 cell_position, int local_index) {
    return cell_position_to_index(cell_position) * cell_size + local_index;
}


// r - [0; 31]
// g - [0; 29]
// b - [0; 31]
// a - []
Unit read_unit_base(int index) {
    uvec4 packed_unit = u_unit_buffer_read.data[index];
    Unit unit;

    unit.substance_id = int(bitfieldExtract(packed_unit.r, 0, 14));
    unit.quantity = int(bitfieldExtract(packed_unit.r, 14, 10));

    unit.momentum.x = int(bitfieldExtract(packed_unit.g, 0, 10) | (bitfieldExtract(packed_unit.b, 0, 6) << 10));
    unit.momentum.y = int(bitfieldExtract(packed_unit.g, 10, 10) | (bitfieldExtract(packed_unit.b, 6, 6) << 10));
    unit.momentum.z = int(bitfieldExtract(packed_unit.g, 20, 10) | (bitfieldExtract(packed_unit.b, 12, 6) << 10));
    unit.momentum -= zero_offset_16;

    unit.plan.quantity = int(bitfieldExtract(packed_unit.r, 24, 8));
    unit.plan.momentum_d = int(bitfieldExtract(packed_unit.b, 18, 14)) - zero_offset_14;

    return unit;
}

Unit read_unit(int global_index) {
    return read_unit_base(global_index);
}

Unit read_unit(ivec3 cell_position, int local_index) {
    return read_unit_base(unit_position_to_index(cell_position, local_index));
}


// todo: Внедрить проверку на переполнение упаковываемых величин, которую можно будет убирать до компиляции, в случае необходимости (макрос для проверки переполнения, который можно отключать #define) 
void write_unit_base(int index, Unit unit) {
    uvec4 packed_unit = uvec4(0);

    packed_unit.r = uint(unit.substance_id);
    packed_unit.r = bitfieldInsert(packed_unit.r, uint(unit.quantity), 14, 10);
    packed_unit.r = bitfieldInsert(packed_unit.r, uint(unit.plan.quantity), 24, 8);

    uvec3 momentum = uvec3(unit.momentum + zero_offset_16);
    packed_unit.g = momentum.x;
    packed_unit.g = bitfieldInsert(packed_unit.g, momentum.y, 10, 10);
    packed_unit.g = bitfieldInsert(packed_unit.g, momentum.z, 20, 10);
    packed_unit.b = momentum.x >> 10;
    packed_unit.b = bitfieldInsert(packed_unit.b, momentum.y >> 10, 6, 6);
    packed_unit.b = bitfieldInsert(packed_unit.b, momentum.z >> 10, 12, 6);
    packed_unit.b = bitfieldInsert(packed_unit.b, uint(unit.plan.momentum_d + zero_offset_14), 18, 14);

    u_unit_buffer_write.data[index] = packed_unit;
}

void write_unit(int global_index, Unit unit) {
    write_unit_base(global_index, unit);
}

void write_unit(ivec3 cell_position, int local_index, Unit unit) {
    write_unit_base(unit_position_to_index(cell_position, local_index), unit);
}
