"""Light levels and the Plejd dim frame.

Minecraft light 0 is an off command. Every brighter step is opcode 0x0098
with the same dim byte written twice, which is the level the Plejd app sends.
"""

from __future__ import annotations


def light_to_dim(light: int) -> int:
    if not isinstance(light, int) or isinstance(light, bool) or not 0 <= light <= 15:
        raise ValueError("light must be an integer 0..15")
    return light * 17


def dim_frame(output_address: int, dim: int) -> bytes:
    if not 0 <= output_address <= 255:
        raise ValueError("output address must be 0..255")
    if not 0 <= dim <= 255:
        raise ValueError("dim must be 0..255")
    if dim == 0:
        return bytes((output_address, 0x01, 0x10, 0x00, 0x97, 0x00))
    return bytes((output_address, 0x01, 0x10, 0x00, 0x98, 0x01, dim, dim))
