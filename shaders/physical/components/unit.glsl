struct Unit {
    uint substance;
    uint quantity;
    vec3 momentum;
};


Unit unpack_unit(uvec4 packed_unit) {
    Unit unit;

    unit.substance = bitfieldExtract(packed_unit.r, 0, 16);
    unit.quantity = bitfieldExtract(packed_unit.r, 16, 16);

    // momentum - импульс одной молекулы вещества
    unit.momentum = (vec3(
    bitfieldExtract(packed_unit.g, 0, 10),
    bitfieldExtract(packed_unit.g, 10, 10),
    bitfieldExtract(packed_unit.g, 20, 10)
    ) - zero_offset_10_bit) / momentum_coeff;

    return unit;
}


// todo: Внедрить проверку на переполнение упаковываемых величин, которую можно будет убирать до компиляции
uvec4 pack_unit(Unit unit) {
    uvec4 packed_unit = uvec4(0);

    packed_unit.r = (unit.substance & mask_16_bit) | ((unit.quantity & mask_16_bit) << 16);

    uvec3 casted_momentum = uvec3(clamp(unit.momentum * momentum_coeff + zero_offset_10_bit, 0.0, float(mask_10_bit)));
    packed_unit.g = (casted_momentum.x & mask_10_bit)
    | ((casted_momentum.y & mask_10_bit) << 10)
    | ((casted_momentum.z & mask_10_bit) << 20);

    return packed_unit;
}
