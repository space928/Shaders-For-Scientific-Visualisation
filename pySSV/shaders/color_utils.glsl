//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
/******************************************************************************
* This file includes a number of functions related to colour space transforms
* and colour maps.
******************************************************************************/


//----------------------------------------------------------------------------------------
// GLSL Color Space Utility Functions
// Taken from: https://github.com/tobspr/GLSL-Color-Spaces/tree/master
/*
GLSL Color Space Utility Functions
(c) 2015 tobspr; modified by Thomas Mathieson

-------------------------------------------------------------------------------

The MIT License (MIT)

Copyright (c) 2015

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
SOFTWARE.

-------------------------------------------------------------------------------

Most formula / matrices are from:
https://en.wikipedia.org/wiki/SRGB

Some are from:
http://www.chilliant.com/rgb2hsv.html
https://www.fourcc.org/fccyvrgb.php
*/


// Define saturation macro, if not already user-defined
#ifndef saturate
/**
* Clamps an input value between 0 and 1 (inclusive).
*
* :param v: the value to clamp.
*/
#define saturate(v) clamp(v, 0, 1)
#endif

// Constants

const float _HCV_EPSILON = 1e-10;
const float _HSL_EPSILON = 1e-10;
const float _HCY_EPSILON = 1e-10;

const float SRGB_GAMMA = 1.0 / 2.2;
const float SRGB_INVERSE_GAMMA = 2.2;
const float SRGB_ALPHA = 0.055;


/**
* Used to convert from linear RGB to XYZ space
*/
const mat3 RGB_2_XYZ = (mat3(
    0.4124564, 0.2126729, 0.0193339,
    0.3575761, 0.7151522, 0.1191920,
    0.1804375, 0.0721750, 0.9503041
));

/**
* Used to convert from XYZ to linear RGB space
*/
const mat3 XYZ_2_RGB = (mat3(
     3.2404542,-0.9692660, 0.0556434,
    -1.5371385, 1.8760108,-0.2040259,
    -0.4985314, 0.0415560, 1.0572252
));

/** The RGB coefficients used to compute luminosity. */
const vec3 LUMA_COEFFS = vec3(0.2126, 0.7152, 0.0722);

/**
* Converts a **linear** rgb colour to its luminance.
*
* :param rgb: the linear rgb value.
* :returns: the linear luminance of the colour.
*/
float luminance(vec3 rgb) {
    return dot(LUMA_COEFFS, rgb);
}

/**
* Converts a linear rgb colour to sRGB using an approximation.
*
* :param rgb: the linear rgb value.
* :returns: the colour in sRGB.
*/
vec3 rgb_to_srgb_approx(vec3 rgb) {
    return pow(rgb, vec3(SRGB_GAMMA));
}

/**
* Converts an sRGB colour to linear rgb using an approximation.
*
* :param rgb: the sRGB colour.
* :returns: the colour in linear rgb.
*/
vec3 srgb_to_rgb_approx(vec3 srgb) {
    return pow(srgb, vec3(SRGB_INVERSE_GAMMA));
}

/**
* Converts a linear value to sRGB.
*
* :param rgb: the linear value.
* :returns: the value in sRGB space.
*/
float linear_to_srgb(float channel) {
    if(channel <= 0.0031308)
        return 12.92 * channel;
    else
        return (1.0 + SRGB_ALPHA) * pow(channel, 1.0/2.4) - SRGB_ALPHA;
}

/**
* Converts an sRGB value to linear space.
*
* :param rgb: the sRGB value.
* :returns: the value in linear space.
*/
float srgb_to_linear(float channel) {
    if (channel <= 0.04045)
        return channel / 12.92;
    else
        return pow((channel + SRGB_ALPHA) / (1.0 + SRGB_ALPHA), 2.4);
}

/**
* Converts a linear rgb colour to sRGB (exact).
*
* :param rgb: the linear rgb value.
* :returns: the colour in sRGB.
*/
vec3 rgb_to_srgb(vec3 rgb) {
    return vec3(
        linear_to_srgb(rgb.r),
        linear_to_srgb(rgb.g),
        linear_to_srgb(rgb.b)
    );
}

/**
* Converts an sRGB colour to linear rgb (exact).
*
* :param rgb: the sRGB colour.
* :returns: the colour in linear rgb.
*/
vec3 srgb_to_rgb(vec3 srgb) {
    return vec3(
        srgb_to_linear(srgb.r),
        srgb_to_linear(srgb.g),
        srgb_to_linear(srgb.b)
    );
}

/** Converts a color from linear RGB to XYZ space */
vec3 rgb_to_xyz(vec3 rgb) {
    return RGB_2_XYZ * rgb;
}

/** Converts a color from XYZ to linear RGB space */
vec3 xyz_to_rgb(vec3 xyz) {
    return XYZ_2_RGB * xyz;
}

/** Converts a color from XYZ to xyY space (Y is luminosity) */
vec3 xyz_to_xyY(vec3 xyz) {
    float Y = xyz.y;
    float x = xyz.x / (xyz.x + xyz.y + xyz.z);
    float y = xyz.y / (xyz.x + xyz.y + xyz.z);
    return vec3(x, y, Y);
}

/** Converts a color from xyY space to XYZ space */
vec3 xyY_to_xyz(vec3 xyY) {
    float Y = xyY.z;
    float x = Y * xyY.x / xyY.y;
    float z = Y * (1.0 - xyY.x - xyY.y) / xyY.y;
    return vec3(x, Y, z);
}

/** Converts a color from linear RGB to xyY space */
vec3 rgb_to_xyY(vec3 rgb) {
    vec3 xyz = rgb_to_xyz(rgb);
    return xyz_to_xyY(xyz);
}

/** Converts a color from xyY space to linear RGB */
vec3 xyY_to_rgb(vec3 xyY) {
    vec3 xyz = xyY_to_xyz(xyY);
    return xyz_to_rgb(xyz);
}

/** Converts a value from linear RGB to HCV (Hue, Chroma, Value) */
vec3 rgb_to_hcv(vec3 rgb)
{
    // Based on work by Sam Hocevar and Emil Persson
    vec4 P = (rgb.g < rgb.b) ? vec4(rgb.bg, -1.0, 2.0/3.0) : vec4(rgb.gb, 0.0, -1.0/3.0);
    vec4 Q = (rgb.r < P.x) ? vec4(P.xyw, rgb.r) : vec4(rgb.r, P.yzx);
    float C = Q.x - min(Q.w, Q.y);
    float H = abs((Q.w - Q.y) / (6.0 * C + _HCV_EPSILON) + Q.z);
    return vec3(H, C, Q.x);
}

/** Converts from pure Hue to linear RGB */
vec3 hue_to_rgb(float hue)
{
    float R = abs(hue * 6.0 - 3.0) - 1.0;
    float G = 2.0 - abs(hue * 6.0 - 2.0);
    float B = 2.0 - abs(hue * 6.0 - 4.0);
    return saturate(vec3(R,G,B));
}

/** Converts from HSV to linear RGB */
vec3 hsv_to_rgb(vec3 hsv)
{
    vec3 rgb = hue_to_rgb(hsv.x);
    return ((rgb - 1.0) * hsv.y + 1.0) * hsv.z;
}

/** Converts from HSL to linear RGB */
vec3 hsl_to_rgb(vec3 hsl)
{
    vec3 rgb = hue_to_rgb(hsl.x);
    float C = (1.0 - abs(2.0 * hsl.z - 1.0)) * hsl.y;
    return (rgb - 0.5) * C + hsl.z;
}

/** Converts from HCY to linear RGB */
vec3 hcy_to_rgb(vec3 hcy)
{
    const vec3 HCYwts = vec3(0.299, 0.587, 0.114);
    vec3 RGB = hue_to_rgb(hcy.x);
    float Z = dot(RGB, HCYwts);
    if (hcy.z < Z) {
        hcy.y *= hcy.z / Z;
    } else if (Z < 1.0) {
        hcy.y *= (1.0 - hcy.z) / (1.0 - Z);
    }
    return (RGB - Z) * hcy.y + hcy.z;
}


/** Converts from linear RGB to HSV */
vec3 rgb_to_hsv(vec3 rgb)
{
    vec3 HCV = rgb_to_hcv(rgb);
    float S = HCV.y / (HCV.z + _HCV_EPSILON);
    return vec3(HCV.x, S, HCV.z);
}

/** Converts from linear rgb to HSL */
vec3 rgb_to_hsl(vec3 rgb)
{
    vec3 HCV = rgb_to_hcv(rgb);
    float L = HCV.z - HCV.y * 0.5;
    float S = HCV.y / (1.0 - abs(L * 2.0 - 1.0) + _HSL_EPSILON);
    return vec3(HCV.x, S, L);
}

/** Converts from rgb to hcy (Hue, Chroma, Luminance) */
vec3 rgb_to_hcy(vec3 rgb)
{
    const vec3 HCYwts = vec3(0.299, 0.587, 0.114);
    // Corrected by David Schaeffer
    vec3 HCV = rgb_to_hcv(rgb);
    float Y = dot(rgb, HCYwts);
    float Z = dot(hue_to_rgb(HCV.x), HCYwts);
    if (Y < Z) {
      HCV.y *= Z / (_HCY_EPSILON + Y);
    } else {
      HCV.y *= (1.0 - Z) / (_HCY_EPSILON + 1.0 - Y);
    }
    return vec3(HCV.x, HCV.y, Y);
}

/** RGB to YCbCr, ranges [0, 1] */
vec3 rgb_to_ycbcr(vec3 rgb) {
    float y = 0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b;
    float cb = (rgb.b - y) * 0.565;
    float cr = (rgb.r - y) * 0.713;

    return vec3(y, cb, cr);
}

/** YCbCr to RGB */
vec3 ycbcr_to_rgb(vec3 yuv) {
    return vec3(
        yuv.x + 1.403 * yuv.z,
        yuv.x - 0.344 * yuv.y - 0.714 * yuv.z,
        yuv.x + 1.770 * yuv.y
    );
}

// Additional conversions converting to rgb first and then to the desired
// color space.

// To srgb
vec3 xyz_to_srgb(vec3 xyz) { return rgb_to_srgb(xyz_to_rgb(xyz)); }
vec3 xyY_to_srgb(vec3 xyY) { return rgb_to_srgb(xyY_to_rgb(xyY)); }
vec3 hue_to_srgb(float hue) { return rgb_to_srgb(hue_to_rgb(hue)); }
vec3 hsv_to_srgb(vec3 hsv) { return rgb_to_srgb(hsv_to_rgb(hsv)); }
vec3 hsl_to_srgb(vec3 hsl) { return rgb_to_srgb(hsl_to_rgb(hsl)); }
vec3 hcy_to_srgb(vec3 hcy) { return rgb_to_srgb(hcy_to_rgb(hcy)); }
vec3 ycbcr_to_srgb(vec3 yuv) { return rgb_to_srgb(ycbcr_to_rgb(yuv)); }

// To xyz
vec3 srgb_to_xyz(vec3 srgb) { return rgb_to_xyz(srgb_to_rgb(srgb)); }
vec3 hue_to_xyz(float hue) { return rgb_to_xyz(hue_to_rgb(hue)); }
vec3 hsv_to_xyz(vec3 hsv) { return rgb_to_xyz(hsv_to_rgb(hsv)); }
vec3 hsl_to_xyz(vec3 hsl) { return rgb_to_xyz(hsl_to_rgb(hsl)); }
vec3 hcy_to_xyz(vec3 hcy) { return rgb_to_xyz(hcy_to_rgb(hcy)); }
vec3 ycbcr_to_xyz(vec3 yuv) { return rgb_to_xyz(ycbcr_to_rgb(yuv)); }

// To xyY
vec3 srgb_to_xyY(vec3 srgb) { return rgb_to_xyY(srgb_to_rgb(srgb)); }
vec3 hue_to_xyY(float hue) { return rgb_to_xyY(hue_to_rgb(hue)); }
vec3 hsv_to_xyY(vec3 hsv) { return rgb_to_xyY(hsv_to_rgb(hsv)); }
vec3 hsl_to_xyY(vec3 hsl) { return rgb_to_xyY(hsl_to_rgb(hsl)); }
vec3 hcy_to_xyY(vec3 hcy) { return rgb_to_xyY(hcy_to_rgb(hcy)); }
vec3 ycbcr_to_xyY(vec3 yuv) { return rgb_to_xyY(ycbcr_to_rgb(yuv)); }

// To HCV
vec3 srgb_to_hcv(vec3 srgb) { return rgb_to_hcv(srgb_to_rgb(srgb)); }
vec3 xyz_to_hcv(vec3 xyz) { return rgb_to_hcv(xyz_to_rgb(xyz)); }
vec3 xyY_to_hcv(vec3 xyY) { return rgb_to_hcv(xyY_to_rgb(xyY)); }
vec3 hue_to_hcv(float hue) { return rgb_to_hcv(hue_to_rgb(hue)); }
vec3 hsv_to_hcv(vec3 hsv) { return rgb_to_hcv(hsv_to_rgb(hsv)); }
vec3 hsl_to_hcv(vec3 hsl) { return rgb_to_hcv(hsl_to_rgb(hsl)); }
vec3 hcy_to_hcv(vec3 hcy) { return rgb_to_hcv(hcy_to_rgb(hcy)); }
vec3 ycbcr_to_hcv(vec3 yuv) { return rgb_to_hcy(ycbcr_to_rgb(yuv)); }

// To HSV
vec3 srgb_to_hsv(vec3 srgb) { return rgb_to_hsv(srgb_to_rgb(srgb)); }
vec3 xyz_to_hsv(vec3 xyz) { return rgb_to_hsv(xyz_to_rgb(xyz)); }
vec3 xyY_to_hsv(vec3 xyY) { return rgb_to_hsv(xyY_to_rgb(xyY)); }
vec3 hue_to_hsv(float hue) { return rgb_to_hsv(hue_to_rgb(hue)); }
vec3 hsl_to_hsv(vec3 hsl) { return rgb_to_hsv(hsl_to_rgb(hsl)); }
vec3 hcy_to_hsv(vec3 hcy) { return rgb_to_hsv(hcy_to_rgb(hcy)); }
vec3 ycbcr_to_hsv(vec3 yuv) { return rgb_to_hsv(ycbcr_to_rgb(yuv)); }

// To HSL
vec3 srgb_to_hsl(vec3 srgb) { return rgb_to_hsl(srgb_to_rgb(srgb)); }
vec3 xyz_to_hsl(vec3 xyz) { return rgb_to_hsl(xyz_to_rgb(xyz)); }
vec3 xyY_to_hsl(vec3 xyY) { return rgb_to_hsl(xyY_to_rgb(xyY)); }
vec3 hue_to_hsl(float hue) { return rgb_to_hsl(hue_to_rgb(hue)); }
vec3 hsv_to_hsl(vec3 hsv) { return rgb_to_hsl(hsv_to_rgb(hsv)); }
vec3 hcy_to_hsl(vec3 hcy) { return rgb_to_hsl(hcy_to_rgb(hcy)); }
vec3 ycbcr_to_hsl(vec3 yuv) { return rgb_to_hsl(ycbcr_to_rgb(yuv)); }

// To HCY
vec3 srgb_to_hcy(vec3 srgb) { return rgb_to_hcy(srgb_to_rgb(srgb)); }
vec3 xyz_to_hcy(vec3 xyz) { return rgb_to_hcy(xyz_to_rgb(xyz)); }
vec3 xyY_to_hcy(vec3 xyY) { return rgb_to_hcy(xyY_to_rgb(xyY)); }
vec3 hue_to_hcy(float hue) { return rgb_to_hcy(hue_to_rgb(hue)); }
vec3 hsv_to_hcy(vec3 hsv) { return rgb_to_hcy(hsv_to_rgb(hsv)); }
vec3 hsl_to_hcy(vec3 hsl) { return rgb_to_hcy(hsl_to_rgb(hsl)); }
vec3 ycbcr_to_hcy(vec3 yuv) { return rgb_to_hcy(ycbcr_to_rgb(yuv)); }

// YCbCr
vec3 srgb_to_ycbcr(vec3 srgb) { return rgb_to_ycbcr(srgb_to_rgb(srgb)); }
vec3 xyz_to_ycbcr(vec3 xyz) { return rgb_to_ycbcr(xyz_to_rgb(xyz)); }
vec3 xyY_to_ycbcr(vec3 xyY) { return rgb_to_ycbcr(xyY_to_rgb(xyY)); }
vec3 hue_to_ycbcr(float hue) { return rgb_to_ycbcr(hue_to_rgb(hue)); }
vec3 hsv_to_ycbcr(vec3 hsv) { return rgb_to_ycbcr(hsv_to_rgb(hsv)); }
vec3 hsl_to_ycbcr(vec3 hsl) { return rgb_to_ycbcr(hsl_to_rgb(hsl)); }
vec3 hcy_to_ycbcr(vec3 hcy) { return rgb_to_ycbcr(hcy_to_rgb(hcy)); }

//----------------------------------------------------------------------------------------
// Color map functions
// Copyright Thomas Mathieson, MIT license
// Based on work from:
// https://bottosson.github.io/posts/oklab/

/**
* Converts a colour from OKLAB space to linear RGB.
*
* https://bottosson.github.io/posts/oklab/
*
* :param lab: the colour in OKLAB space.
* :returns: the colour in linear rgb.
*/
vec3 oklab_to_rgb(const vec3 lab) {
    const mat3 lab2lms = mat3(
        1., 1., 1.,
        0.3963377774, -0.1055613458, -0.0894841775,
        0.2158037573, -0.0638541728, -1.2914855480
    );
    const mat3 lms2rgb = mat3(
        +4.0767416621, -1.2684380046, -0.0041960863,
        -3.3077115913, +2.6097574011, -0.7034186147,
        +0.2309699292, -0.3413193965, +1.7076147010
    );
    vec3 lms = lab2lms * lab;
    lms = lms*lms*lms;

	return lms2rgb * lms;
}

/**
* Converts a colour from linear RGB space to OKLAB.
*
* https://bottosson.github.io/posts/oklab/
*
* :param rgb: the colour in linear rgb.
* :returns: the colour in OKLAB space.
*/
vec3 rgb_to_oklab(const vec3 rgb) {
    const mat3 lab2lms = mat3(
        0.4122214708, 0.2119034982, 0.0883024619,
        0.5363325363, 0.6806995451, 0.2817188376,
        0.0514459929, 0.1073969566, 0.6299787005
    );
    const mat3 lms2rgb = mat3(
        +0.2104542553, +1.9779984951, +0.0259040371,
        +0.7936177850, -2.4285922050, +0.7827717662,
        -0.0040720468, +0.4505937099, -0.8086757660
    );
    vec3 lms = lab2lms * rgb;
    lms = pow(lms, vec3(1./3.));

	return lms2rgb * lms;
}

//----------------------------------------------------------------------------------------
// Color map functions
// Copyright Thomas Mathieson, MIT license

/**
* Maps a value between [0-1] to a colour.
*
* Maps from black to white.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_greys(float x) {
    //return vec3(pow(saturate(x), SRGB_INVERSE_GAMMA));
    return vec3(saturate(x));
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from ``oklabCol`` to white.
*
* :param x: the value to colour map.
* :param oklabCol: the base colour to use in OKLAB space.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_tinted(float x, vec3 oklabCol) {
    vec3 lab = oklabCol;
    lab = mix(lab, vec3(1., 0., 0.), saturate(x));
    return oklab_to_rgb(lab);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from ``oklabColA`` to ``oklabColB`` (linear interpolation in OKLAB space).
*
* :param x: the value to colour map.
* :param oklabColA: the start colour to use in OKLAB space.
* :param oklabColB: the end colour to use in OKLAB space.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_mix(float x, vec3 oklabColA, vec3 oklabColB) {
    vec3 lab = mix(oklabColA, oklabColB, saturate(x));
    return oklab_to_rgb(lab);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from ``oklabColA`` to ``oklabColB`` to ``oklabColC`` (linear interpolation in OKLAB space).
*
* :param x: the value to colour map.
* :param oklabColA: the start colour to use in OKLAB space.
* :param oklabColB: the middle colour to use in OKLAB space.
* :param oklabColC: the end colour to use in OKLAB space.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_mix_3(float x, vec3 oklabColA, vec3 oklabColB, vec3 oklabColC) {
    float x0 = saturate(x) * 2.;
    float x1 = fract(x0);
    vec3 lab = oklabColA;
    if (x0 < 1.) {
        lab = mix(oklabColA, oklabColB, x1);
    } else {
        lab = mix(oklabColB, oklabColC, x1);
    }
    return oklab_to_rgb(lab);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from purple to white.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_purples(float x) {
    return colmap_tinted(x, vec3(0., 0.354, -0.354));
    /*x = saturate(x);
    return vec3(0.2, 0., 0.4)*(1.-x)+vec3(x);*/
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from blue to white.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_blues(float x) {
    return colmap_tinted(x, vec3(0., -0.05, -0.3));
    /*x = saturate(x);
    return vec3(0.0, 0.08, 0.4)*(1.-x)+vec3(x);*/
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from green to white.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_greens(float x) {
    return colmap_tinted(x, vec3(0.25, -0.270, 0.196));
    /*x = saturate(x);
    return vec3(0.0, 0.2, 0.02)*(1.-x)+vec3(x);*/
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from orange to white.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_oranges(float x) {
    return colmap_tinted(x, vec3(0.35, 0., 0.333));
    /*x = saturate(x);
    return vec3(0.4, 0.3, 0.0)*(1.-x)+vec3(x);*/
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from red to white.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_reds(float x) {
    return colmap_tinted(x, vec3(0.25, 0.223, 0.113));
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from pink to white to green.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_PiYG(float x) {
    const vec3 c0 = vec3(0.35, 0.3, -0.1);
    const vec3 c1 = vec3(.95, 0., 0.);
    const vec3 c2 = vec3(.5, -.27, .20);
    return colmap_mix_3(x, c0, c1, c2);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from purple to white to green.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_PRGn(float x) {
    const vec3 c0 = vec3(0.2, 0.3, -0.25);
    const vec3 c1 = vec3(.95, 0., 0.);
    const vec3 c2 = vec3(.4, -.27, .20);
    return colmap_mix_3(x, c0, c1, c2);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from orange to white to purple.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_PuOr(float x) {
    const vec3 c0 = vec3(0.45, 0.1, 0.4);
    const vec3 c1 = vec3(.95, 0., 0.);
    const vec3 c2 = vec3(.4, .3, -.25);
    return colmap_mix_3(x, c0, c1, c2);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from red to white to blue.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_RdBu(float x) {
    const vec3 c0 = vec3(0.3, 0.4, 0.0);
    const vec3 c1 = vec3(.95, 0., 0.);
    const vec3 c2 = vec3(.4, .0, -.2);
    return colmap_mix_3(x, c0, c1, c2);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from blue to red.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_coolwarm(float x) {
    x = saturate(x);
    const vec3 c0 = vec3(.2, .2, 0.9);
    const vec3 c1 = vec3(0.9, .2, .2);
    return mix(c0, c1, x);
    /*const vec3 c0 = vec3(.7, .0, -.15);
    const vec3 c1 = vec3(0.75, 0., 0.0);
    const vec3 c2 = vec3(0.6, 0.4, 0.0);
    return colmap_mix_3(x, c0, c1, c2);*/
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from purple to green to yellow. Looks a bit like viridis.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_PurGnYl(float x) {
    const vec3 c0 = vec3(0.39, 0.25, -0.202);
    const vec3 c1 = vec3(0.70, -0.12, 0.03);
    const vec3 c2 = vec3(.95, -0.077, 0.238);
    return colmap_mix_3(x, c0, c1, c2);
}

/**
* Maps a value between [0-1] to a colour.
*
* Maps from white to blue to black to red and back to white.
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_twilight(float x) {
    const vec3 c0 = vec3(0.8, 0.0, 0.0);
    const vec3 c1 = vec3(.5, 0., -.2);
    const vec3 c2 = vec3(.1, .0, 0.);
    const vec3 c3 = vec3(.5, .18, 0.05);
    float x0 = saturate(x) * 4.;
    float x1 = fract(x0);
    vec3 lab = c0;
    if (x0 < 1.) {
        lab = mix(c0, c1, x1);
    } else if (x0 < 2.) {
        lab = mix(c1, c2, x1);
    } else if (x0 < 3.) {
        lab = mix(c2, c3, x1);
    } else {
        lab = mix(c3, c0, x1);
    }
    return rgb_to_srgb_approx(oklab_to_rgb(lab));
}

// The viridis family of colourmaps are adapted from:
// https://www.shadertoy.com/view/WlfXRN
// CC0 license
/**
* Maps a value between [0-1] to a colour.
*
* This is an approximation of the popular 'viridis' colormap taken from:
* https://www.shadertoy.com/view/WlfXRN
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_viridis(float t) {
    t = saturate(t);
    const vec3 c0 = vec3(0.2777273272234177, 0.005407344544966578, 0.3340998053353061);
    const vec3 c1 = vec3(0.1050930431085774, 1.404613529898575, 1.384590162594685);
    const vec3 c2 = vec3(-0.3308618287255563, 0.214847559468213, 0.09509516302823659);
    const vec3 c3 = vec3(-4.634230498983486, -5.799100973351585, -19.33244095627987);
    const vec3 c4 = vec3(6.228269936347081, 14.17993336680509, 56.69055260068105);
    const vec3 c5 = vec3(4.776384997670288, -13.74514537774601, -65.35303263337234);
    const vec3 c6 = vec3(-5.435455855934631, 4.645852612178535, 26.3124352495832);

    return c0+t*(c1+t*(c2+t*(c3+t*(c4+t*(c5+t*c6)))));
}

/**
* Maps a value between [0-1] to a colour.
*
* This is an approximation of the popular 'plasma' colormap taken from:
* https://www.shadertoy.com/view/WlfXRN
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_plasma(float t) {
    t = saturate(t);
    const vec3 c0 = vec3(0.05873234392399702, 0.02333670892565664, 0.5433401826748754);
    const vec3 c1 = vec3(2.176514634195958, 0.2383834171260182, 0.7539604599784036);
    const vec3 c2 = vec3(-2.689460476458034, -7.455851135738909, 3.110799939717086);
    const vec3 c3 = vec3(6.130348345893603, 42.3461881477227, -28.51885465332158);
    const vec3 c4 = vec3(-11.10743619062271, -82.66631109428045, 60.13984767418263);
    const vec3 c5 = vec3(10.02306557647065, 71.41361770095349, -54.07218655560067);
    const vec3 c6 = vec3(-3.658713842777788, -22.93153465461149, 18.19190778539828);

    return c0+t*(c1+t*(c2+t*(c3+t*(c4+t*(c5+t*c6)))));
}

/**
* Maps a value between [0-1] to a colour.
*
* This is an approximation of the popular 'magma' colormap taken from:
* https://www.shadertoy.com/view/WlfXRN
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_magma(float t) {
    t = saturate(t);
    const vec3 c0 = vec3(-0.002136485053939582, -0.000749655052795221, -0.005386127855323933);
    const vec3 c1 = vec3(0.2516605407371642, 0.6775232436837668, 2.494026599312351);
    const vec3 c2 = vec3(8.353717279216625, -3.577719514958484, 0.3144679030132573);
    const vec3 c3 = vec3(-27.66873308576866, 14.26473078096533, -13.64921318813922);
    const vec3 c4 = vec3(52.17613981234068, -27.94360607168351, 12.94416944238394);
    const vec3 c5 = vec3(-50.76852536473588, 29.04658282127291, 4.23415299384598);
    const vec3 c6 = vec3(18.65570506591883, -11.48977351997711, -5.601961508734096);

    return c0+t*(c1+t*(c2+t*(c3+t*(c4+t*(c5+t*c6)))));
}

/**
* Maps a value between [0-1] to a colour.
*
* This is an approximation of the popular 'inferno' colormap taken from:
* https://www.shadertoy.com/view/WlfXRN
*
* :param x: the value to colour map.
* :returns: the colour mapped to the given value.
*/
vec3 colmap_inferno(float t) {
    t = saturate(t);
    const vec3 c0 = vec3(0.0002189403691192265, 0.001651004631001012, -0.01948089843709184);
    const vec3 c1 = vec3(0.1065134194856116, 0.5639564367884091, 3.932712388889277);
    const vec3 c2 = vec3(11.60249308247187, -3.972853965665698, -15.9423941062914);
    const vec3 c3 = vec3(-41.70399613139459, 17.43639888205313, 44.35414519872813);
    const vec3 c4 = vec3(77.162935699427, -33.40235894210092, -81.80730925738993);
    const vec3 c5 = vec3(-71.31942824499214, 32.62606426397723, 73.20951985803202);
    const vec3 c6 = vec3(25.13112622477341, -12.24266895238567, -23.07032500287172);

    return c0+t*(c1+t*(c2+t*(c3+t*(c4+t*(c5+t*c6)))));
}
