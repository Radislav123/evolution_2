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


// r - [0; 31]
// g - [0; 29]
// b - [0; 31]
// a - []
Unit unpack_unit(uvec4 packed_unit) {
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


// todo: Внедрить проверку на переполнение упаковываемых величин, которую можно будет убирать до компиляции, в случае необходимости
//  макрос для проверки переполнения, который можно отключать #define
uvec4 pack_unit(Unit unit) {
    uvec4 packed_unit = uvec4(0);

    packed_unit.r = (uint(unit.substance_id) & mask_14) | ((uint(unit.quantity) & mask_10) << 14)
    | ((uint(unit.plan.quantity) & mask_8) << 24);

    uvec3 momentum = uvec3(unit.momentum + zero_offset_16);
    packed_unit.g = (momentum.x & mask_10) | ((momentum.y & mask_10) << 10) | ((momentum.z & mask_10) << 20);
    packed_unit.b = (momentum.x >> 10 & mask_6) | ((momentum.y >> 10 & mask_6) << 6) | ((momentum.z >> 10 & mask_6) << 12)
    | ((uint(unit.plan.momentum_d + zero_offset_14) & mask_14) << 18);

    return packed_unit;
}
