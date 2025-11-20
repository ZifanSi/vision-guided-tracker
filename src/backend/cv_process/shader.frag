#version 100
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;
uniform float tx;
uniform float ty;
uniform float scale;

// this shader performs these operations in order:
// 1. translate by (tx, ty)
// 2. rotate clockwise 90 degrees
// 3. scale by s around center
void main() {
    float pixel_size_x = 1.0 / 1920.0;
    float pixel_size_y = 1.0 / 1080.0;
    float cw = 9.0 / 16.0;
    float bw = (1.0 - cw) * 0.5;
    float ch = 16.0 / 9.0;
    float bh = (ch - 1.0) * 0.5;

    float x3 = v_texcoord.x;
    float y3 = v_texcoord.y;

    float x2 = 0.5 + (x3 - 0.5) / scale;
    float y2 = 0.5 - (0.5 - y3) / scale;

    float x1 = (y2 + bh) / ch;
    float y1 = 1.0 - (x2 - bw) / cw;

    float x0 = x1 - tx;
    float y0 = y1 - ty;


    if (x0 >= 0.0 && x0 <= 1.0 && (y0 < 0.0 || y0 > 1.0)) {
        // horizontal edge blur
        y0 = clamp(y0, 0.0, 1.0);

        vec4 accum = vec4(0.0);
        float count = 0.0;
        for (int i = -50; i <= 50; i += 5) {
            float sampleX = x0 + float(i) * pixel_size_x / scale;

            vec2 src;
            src.x = sampleX;
            src.y = y0;
            float weight = 1.0 - abs(float(i)) / 50.0;
            accum += texture2D(tex, src) * weight;
            count += weight;
        }

        gl_FragColor = accum / count;
        return;
    }

    vec2 src;
    src.x = clamp(x0, 0.0, 1.0);
    src.y = clamp(y0, 0.0, 1.0);
    gl_FragColor = texture2D(tex, src);
}