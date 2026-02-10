layout(std430, binding = 1) readonly restrict buffer ReadPlan {
    usampler3D handles[];
} u_read_plan;
layout(std430, binding = 6) writeonly restrict buffer WritePlan {
    uimage3D handles[];
} u_write_plan;


struct Plan {
// Ось соседа == world_age % 3
// Наличие планов в юнитах ([0; 31], [32; 63])
    uvec2 presence;
// Направление планов
    uvec2 direction;
};


Plan new_plan() {
    return Plan(uvec2(0u), uvec2(0u));
}


Plan read_plan(ivec3 position) {
    int chunk_index = 0;
    uvec4 packed_plan = texelFetch(u_read_plan.handles[chunk_index], position, 0);
    Plan plan;

    plan.presence = packed_plan.rg;
    plan.direction = packed_plan.ba;

    return plan;
}


void write_plan(ivec3 position, Plan plan) {
    int chunk_index = 0;
    uvec4 packed_plan = uvec4(0u);

    packed_plan.rg = plan.presence;
    packed_plan.ba = plan.direction;

    imageStore(u_write_plan.handles[chunk_index], position, packed_plan);
}
