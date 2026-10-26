package ke.brek.plejdlight;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class LightScaleTest {
    @Test
    void mapsEachLightStepOntoADistinctDimByte() {
        int[] expected = {0, 17, 34, 51, 68, 85, 102, 119, 136, 153, 170, 187, 204, 221, 238, 255};
        for (int light = 0; light <= 15; light++) {
            assertEquals(expected[light], LightScale.dimByte(light));
            assertEquals(Math.round(light / 15f * 255f), LightScale.dimByte(light));
        }
    }

    @Test
    void invertFlipsTheEndsAndLeavesTheMiddle() {
        assertEquals(15, LightScale.applyInvert(0, true));
        assertEquals(0, LightScale.applyInvert(15, true));
        assertEquals(8, LightScale.applyInvert(7, true));
        assertEquals(4, LightScale.applyInvert(4, false));
    }

    @Test
    void rejectsLevelsOutsideMinecraftLight() {
        assertThrows(IllegalArgumentException.class, () -> LightScale.dimByte(-1));
        assertThrows(IllegalArgumentException.class, () -> LightScale.dimByte(16));
        assertThrows(IllegalArgumentException.class, () -> LightScale.applyInvert(16, false));
    }
}
