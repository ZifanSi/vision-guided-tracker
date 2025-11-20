#version 100
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

void main() {
    // Input: 1920x1080 (16:9)
    // Rotated: 1080x1920 (9:16)
    // Output: 1920x1080 (16:9)
    // Rotated image is letterboxed horizontally.

    float outputAspect  = 16.0 / 9.0;
    float rotatedAspect = 9.0 / 16.0;
    float contentWidth  = rotatedAspect / outputAspect; // normalized width of rotated content
    float border        = (1.0 - contentWidth) * 0.5;

    float s = v_texcoord.x;
    float t = v_texcoord.y;

    // Common vertical coord in rotated space
    float Y = clamp(t, 0.0, 1.0);

    // Inside content region: just rotate and sample normally
    if (s >= border && s <= 1.0 - border) {
        float X = (s - border) / contentWidth; // 0..1 across rotated image
        X = clamp(X, 0.0, 1.0);

        // Rotate 90° clockwise: (X, Y) -> (Y, 1 - X)
        vec2 src;
        src.x = Y;
        src.y = 1.0 - X;

        gl_FragColor = texture2D(tex, src);
        return;
    }

    // Border region: vertical blur using edge pixels of rotated image

    bool isLeft = (s < border);
    float X_edge = isLeft ? 0.0 : 1.0;

    // Vertical texel size in 1080p
    float texelSize = 1.0 / 1080.0;

    vec4 accum = vec4(0.0);
    float count = 0.0;

    for (int i = -50; i <= 50; i += 5) {
        float sampleY = clamp(Y + float(i) * texelSize, 0.0, 1.0);

        // Rotated coords: (X_edge, sampleY) -> (sampleY, 1 - X_edge)
        vec2 src;
        src.x = sampleY;
        src.y = 1.0 - X_edge;

        accum += texture2D(tex, src);
        count += 1.0;
    }

    gl_FragColor = accum / count;
}