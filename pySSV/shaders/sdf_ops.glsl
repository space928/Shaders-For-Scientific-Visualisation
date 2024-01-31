//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.

// SDF combination operators
float op_not(float a) {
    return -a;
}

float op_union(float a, float b) {
    return min(a, b);
}

float op_intersect(float a, float b) {
    return max(a, b);
}

float op_subtract(float a, float b) {
    return op_intersect(a, op_not(b));
}

float op_xor(float a, float b) {
    return op_intersect(op_union(a, b), -op_intersect(a, b));
}

// polynomial smooth min
// https://iquilezles.org/articles/smin/
float op_sminCubic(float a, float b, float k)
{
    float h = max(k - abs(a - b), 0.0)/k;
    return min(a, b) - h*h*h*k*(1.0/6.0);
}

float op_smaxCubic(float a, float b, float k)
{
    float h = max(k - abs(a - b), 0.0)/k;
    return max(a, b) + h*h*h*k*(1.0/6.0);
}

float op_smooth_union(float a, float b, float k) {
    return op_sminCubic(a, b, k);
}

float op_smooth_intersect(float a, float b, float k) {
    return op_smaxCubic(a, b, k);
}

float op_smooth_subtract(float a, float b, float k) {
    return op_smooth_intersect(a, op_not(b), k);
}

float op_smooth_xor(float a, float b, float k) {
    return op_smooth_intersect(op_smooth_union(a, b, k), -op_smooth_intersect(a, b, k), k);
}
