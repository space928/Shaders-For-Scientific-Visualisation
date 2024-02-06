//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
/******************************************************************************
* This file includes a number of functions related to random number generation,
* hashing, and screen space dithering.
******************************************************************************/

//----------------------------------------------------------------------------------------
// Hash without Sine
// Taken from: https://www.shadertoy.com/view/4djSRW
/* Copyright (c)2014 David Hoskins.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.*/

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``float``.
* :returns: the hash of p as a ``float``.
*/
float hash11(float p)
{
    p = fract(p * .1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec2``.
* :returns: the hash of p as a ``float``.
*/
float hash12(vec2 p)
{
	vec3 p3  = fract(vec3(p.xyx) * .1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec3``.
* :returns: the hash of p as a ``float``.
*/
float hash13(vec3 p3)
{
	p3  = fract(p3 * .1031);
    p3 += dot(p3, p3.zyx + 31.32);
    return fract((p3.x + p3.y) * p3.z);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec4``.
* :returns: the hash of p as a ``float``.
*/
float hash14(vec4 p4)
{
	p4 = fract(p4  * vec4(.1031, .1030, .0973, .1099));
    p4 += dot(p4, p4.wzxy+33.33);
    return fract((p4.x + p4.y) * (p4.z + p4.w));
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``float``.
* :returns: the hash of p as a ``vec2``.
*/
vec2 hash21(float p)
{
	vec3 p3 = fract(vec3(p) * vec3(.1031, .1030, .0973));
	p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx+p3.yz)*p3.zy);

}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec2``.
* :returns: the hash of p as a ``vec2``.
*/
vec2 hash22(vec2 p)
{
	vec3 p3 = fract(vec3(p.xyx) * vec3(.1031, .1030, .0973));
    p3 += dot(p3, p3.yzx+33.33);
    return fract((p3.xx+p3.yz)*p3.zy);

}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec3``.
* :returns: the hash of p as a ``vec2``.
*/
vec2 hash23(vec3 p3)
{
	p3 = fract(p3 * vec3(.1031, .1030, .0973));
    p3 += dot(p3, p3.yzx+33.33);
    return fract((p3.xx+p3.yz)*p3.zy);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``float``.
* :returns: the hash of p as a ``vec3``.
*/
vec3 hash31(float p)
{
   vec3 p3 = fract(vec3(p) * vec3(.1031, .1030, .0973));
   p3 += dot(p3, p3.yzx+33.33);
   return fract((p3.xxy+p3.yzz)*p3.zyx);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec2``.
* :returns: the hash of p as a ``vec3``.
*/
vec3 hash32(vec2 p)
{
	vec3 p3 = fract(vec3(p.xyx) * vec3(.1031, .1030, .0973));
    p3 += dot(p3, p3.yxz+33.33);
    return fract((p3.xxy+p3.yzz)*p3.zyx);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec3``.
* :returns: the hash of p as a ``vec3``.
*/
vec3 hash33(vec3 p3)
{
	p3 = fract(p3 * vec3(.1031, .1030, .0973));
    p3 += dot(p3, p3.yxz+33.33);
    return fract((p3.xxy + p3.yxx)*p3.zyx);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``float``.
* :returns: the hash of p as a ``vec4``.
*/
vec4 hash41(float p)
{
	vec4 p4 = fract(vec4(p) * vec4(.1031, .1030, .0973, .1099));
    p4 += dot(p4, p4.wzxy+33.33);
    return fract((p4.xxyz+p4.yzzw)*p4.zywx);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec2``.
* :returns: the hash of p as a ``vec4``.
*/
vec4 hash42(vec2 p)
{
	vec4 p4 = fract(vec4(p.xyxy) * vec4(.1031, .1030, .0973, .1099));
    p4 += dot(p4, p4.wzxy+33.33);
    return fract((p4.xxyz+p4.yzzw)*p4.zywx);

}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec3``.
* :returns: the hash of p as a ``vec4``.
*/
vec4 hash43(vec3 p)
{
	vec4 p4 = fract(vec4(p.xyzx) * vec4(.1031, .1030, .0973, .1099));
    p4 += dot(p4, p4.wzxy+33.33);
    return fract((p4.xxyz+p4.yzzw)*p4.zywx);
}

/**
* Hashes the given input. Uses the "Hash without Sine" algorithm (https://www.shadertoy.com/view/4djSRW).
* Tends to fail with small changes in p.
*
* :param p: the input to the hash function as a ``vec4``.
* :returns: the hash of p as a ``vec4``.
*/
vec4 hash44(vec4 p4)
{
	p4 = fract(p4 * vec4(.1031, .1030, .0973, .1099));
    p4 += dot(p4, p4.wzxy+33.33);
    return fract((p4.xxyz+p4.yzzw)*p4.zywx);
}
//----------------------------------------------------------------------------------------
// PCG family of random number generators
// https://www.jcgt.org/published/0009/03/02/
// https://www.pcg-random.org/
// Available under the Apache 2.0 license
/**
* Hashes the given input. Uses the PCG algorithm (https://www.pcg-random.org/).
* This algorithm strikes a very good balance between performance and high quality hashing.
*
* :param v: the input to the hash function as a ``uint``.
* :returns: the hash of p as a ``uint``.
*/
uint pcg(uint v)
{
	uint state = v * 747796405u + 2891336453u;
	uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
	return (word >> 22u) ^ word;
}

/**
* Hashes the given input. Uses the PCG algorithm (https://www.pcg-random.org/).
* This algorithm strikes a very good balance between performance and high quality hashing.
*
* :param v: the input to the hash function as a ``uvec2``.
* :returns: the hash of p as a ``uvec2``.
*/
uvec2 pcg2d(uvec2 v)
{
    v = v * 1664525u + 1013904223u;

    v.x += v.y * 1664525u;
    v.y += v.x * 1664525u;

    v = v ^ (v>>16u);

    v.x += v.y * 1664525u;
    v.y += v.x * 1664525u;

    v = v ^ (v>>16u);

    return v;
}

/**
* Hashes the given input. Uses the PCG algorithm (https://www.pcg-random.org/).
* This algorithm strikes a very good balance between performance and high quality hashing.
*
* :param v: the input to the hash function as a ``uvec3``.
* :returns: the hash of p as a ``uvec3``.
*/
uvec3 pcg3d(uvec3 v) {
    v = v * 1664525u + 1013904223u;

    v.x += v.y*v.z;
    v.y += v.z*v.x;
    v.z += v.x*v.y;

    v ^= v >> 16u;

    v.x += v.y*v.z;
    v.y += v.z*v.x;
    v.z += v.x*v.y;

    return v;
}

/**
* Hashes the given input. Uses the PCG algorithm (https://www.pcg-random.org/).
* This algorithm strikes a very good balance between performance and high quality hashing.
*
* :param v: the input to the hash function as a ``uvec4``.
* :returns: the hash of p as a ``uvec4``.
*/
uvec4 pcg4d(uvec4 v)
{
    v = v * 1664525u + 1013904223u;

    v.x += v.y*v.w;
    v.y += v.z*v.x;
    v.z += v.x*v.y;
    v.w += v.y*v.z;

    v ^= v >> 16u;

    v.x += v.y*v.w;
    v.y += v.z*v.x;
    v.z += v.x*v.y;
    v.w += v.y*v.z;

    return v;
}

//----------------------------------------------------------------------------------------
// Dithering functions
// Copyright Thomas Mathieson, MIT License
/**
* Dithers the input colour using triangular distributed value noise.
*
* :param col: the colour to dither.
* :param p: the screen-space position in pixels.
* :param bits: how many least significant bits should be dithered.
* :returns: the dithered colour.
*/
vec3 _dither_col(vec3 col, vec2 p, const int bits) {
    //vec3 dither = vec3((hash12(p)*2.-1.)); // Uniform dist
    vec3 dither = vec3((hash12(p)+hash12(p+0.593743)-.5)); // Triangular dist
    vec3 c = col + dither/float(1<<(bits));
    //c = floor(c.rgb * float(1<<(bits))) / float(1<<(bits));
    return c;
}

/**
* Dithers the input colour using Valve's ordered dithering algorithm.
* http://alex.vlachos.com/graphics/Alex_Vlachos_Advanced_VR_Rendering_GDC2015.pdf
*
* :param col: the colour to dither.
* :param p: the screen-space position in pixels.
* :param bits: how many least significant bits should be dithered.
* :returns: the dithered colour.
*/
vec3 _dither_col_ordered(vec3 col, vec2 p, const int bits) {
    vec3 dither = vec3(dot(vec2(171.0, 231.0), p));
    dither = fract(dither.rgb / vec3(103.0, 71.0, 97.0));
    vec3 c = col + dither/float(1<<(bits));
    //c = floor(c.rgb * float(1<<(bits))) / float(1<<(bits));
    return c;
}

/**
* Dithers the input colour using triangular distributed value noise. Dithers to 8 bit per pixel precision (256 values).
*
* :param col: the colour to dither.
* :param p: the screen-space position in pixels.
* :returns: the dithered colour.
*/
vec3 dither_col(vec3 col, vec2 p) {
    return _dither_col(col, p, 8);
}

/**
* Dithers the input colour using Valve's ordered dithering algorithm. Dithers to 8 bit per pixel precision (256 values).
* http://alex.vlachos.com/graphics/Alex_Vlachos_Advanced_VR_Rendering_GDC2015.pdf
*
* :param col: the colour to dither.
* :param p: the screen-space position in pixels.
* :returns: the dithered colour.
*/
vec3 dither_col_ordered(vec3 col, vec2 p) {
    return _dither_col_ordered(col, p, 8);
}
