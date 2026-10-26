package ke.brek.plejdlight;

/**
 * Maps a Minecraft light level onto a Plejd dim byte.
 * 255 / 15 = 17, so each step is exact and matches the Python bridge.
 */
public final class LightScale {
    private LightScale() {}

    public static int dimByte(int light) {
        requireLight(light);
        return light * 17;
    }

    public static int applyInvert(int light, boolean invert) {
        requireLight(light);
        return invert ? 15 - light : light;
    }

    private static void requireLight(int light) {
        if (light < 0 || light > 15) {
            throw new IllegalArgumentException("light must be 0..15");
        }
    }
}
