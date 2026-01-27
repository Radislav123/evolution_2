#version 460
#extension GL_ARB_bindless_texture : require


layout(std430, binding = 1) writeonly restrict buffer WorldCellWrite {
    uimage3D handles[];
} u_world_cell_write;
layout(std430, binding = 2) writeonly restrict buffer WorldBlockWrite {
    uimage3D handles[];
} u_world_block_write;
layout(std430, binding = 3) writeonly restrict buffer WorldUnitWrite {
    uimage3D handles[];
} u_world_unit_write;


#include physical_constants
#include packing_constants
#include cell
#include unit


// todo: Реализовать генерацию мира тут
void main() {

}
