struct Unit {
    int substance;
    int quantity;
// Импульс всего юнита
// Сейчас каждый компонент может занимать до 21 бита
    ivec3 momentum;
};


Unit new_unit() {
    return Unit(0, 0, ivec3(0));
}


Unit unpack_unit(uvec4 packed_unit) {
    Unit unit;

    unit.substance = int(bitfieldExtract(packed_unit.r, 0, 16));
    unit.quantity = int(bitfieldExtract(packed_unit.r, 16, 16));

    unit.momentum.x = int(bitfieldExtract(packed_unit.g, 0, 16) | (bitfieldExtract(packed_unit.b, 16, 5) << 16));
    unit.momentum.y = int(bitfieldExtract(packed_unit.g, 16, 16) | (bitfieldExtract(packed_unit.b, 21, 5) << 16));
    unit.momentum.z = int(bitfieldExtract(packed_unit.b, 0, 16) | (bitfieldExtract(packed_unit.b, 26, 5) << 16));
    unit.momentum -= int(zero_offset_21);

    return unit;
}


// todo: Внедрить проверку на переполнение упаковываемых величин, которую можно будет убирать до компиляции, в случае необходимости
//  макрос для проверки переполнения, который можно отключать #define
uvec4 pack_unit(Unit unit) {
    uvec4 packed_unit = uvec4(0);

    packed_unit.r = (uint(unit.substance) & mask_16) | ((uint(unit.quantity) & mask_16) << 16);

    uvec3 momentum = uvec3(unit.momentum + zero_offset_21);
    packed_unit.g = (momentum.x & mask_16) | ((momentum.y & mask_16) << 16);
    packed_unit.b = (momentum.z & mask_16)
    | ((momentum.x >> 16 & mask_5) << 16) | ((momentum.y >> 16 & mask_5) << 21) | ((momentum.z >> 16 & mask_5) << 26);

    return packed_unit;
}
