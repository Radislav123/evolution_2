struct SubstanceOptics {
    vec3 color;
    float absorption;
};


layout(std430, binding = 20) readonly restrict buffer SubstanceOpticsBuffer {
    SubstanceOptics data[];
} u_substance_optics_buffer;


SubstanceOptics read_substance_optics(int substance_id) {
    return u_substance_optics_buffer.data[substance_id];
}
