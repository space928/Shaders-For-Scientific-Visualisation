uniform float uTime;
uniform vec4 uResolution;
uniform vec2 uMouse;

#ifdef SHADERTOY_COMPAT
#define iTime uTime
#define iResolution uResolution
#define iMouse uMouse
#endif
