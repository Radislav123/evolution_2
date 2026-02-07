struct Substance {
    int mass;
};


layout(std430, binding = 10) readonly restrict buffer SubstanceBuffer {
    Substance data[];
} u_substance_buffer;


Substance read_substance(int substance_id) {
    return u_substance_buffer.data[substance_id];
}
