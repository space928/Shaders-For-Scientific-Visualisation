//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
/******************************************************************************
* This file includes a number of functions related to signed distance field
* operations.
******************************************************************************/

// SDF combination operators
/**
* Inverts a signed distance field. (Logical NOT)
*
* :param a: the sdf to invert.
* :returns: the new sdf.
*/
float op_not(float a) {
    return -a;
}

/**
* Computes the union between two distance fields. (logical OR)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :returns: the combined sdf.
*/
float op_union(float a, float b) {
    return min(a, b);
}

/**
* Computes the intersection between two distance fields. (logical AND)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :returns: the combined sdf.
*/
float op_intersect(float a, float b) {
    return max(a, b);
}

/**
* Computes the difference between two distance fields. (logical SUBTRACT)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :returns: the combined sdf.
*/
float op_subtract(float a, float b) {
    return op_intersect(a, op_not(b));
}

/**
* Computes the exclusive OR between two distance fields. (logical XOR)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :returns: the combined sdf.
*/
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

/**
* Computes the union between two distance fields with a soft intersection. (logical OR)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :param k: the amount of smoothing to apply to the intersection.
* :returns: the combined sdf.
*/
float op_smoothUnion(float a, float b, float k) {
    return op_sminCubic(a, b, k);
}

/**
* Computes the intersection between two distance fields with a soft intersection. (logical AND)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :param k: the amount of smoothing to apply to the intersection.
* :returns: the combined sdf.
*/
float op_smoothIntersect(float a, float b, float k) {
    return op_smaxCubic(a, b, k);
}

/**
* Computes the difference between two distance fields with a soft intersection. (logical SUBTRACT)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :param k: the amount of smoothing to apply to the intersection.
* :returns: the combined sdf.
*/
float op_smoothSubtract(float a, float b, float k) {
    return op_smoothIntersect(a, op_not(b), k);
}

/**
* Computes the exclusive OR between two distance fields with a soft intersection. (logical XOR)
*
* :param a: the first sdf.
* :param b: the second sdf.
* :param k: the amount of smoothing to apply to the intersection.
* :returns: the combined sdf.
*/
float op_smoothXor(float a, float b, float k) {
    return op_smoothIntersect(op_smoothUnion(a, b, k), -op_smoothIntersect(a, b, k), k);
}
