"""
generate_bell.py
Generates a crystal-clear, loud 1.6-second two-tone reception bell ("Ding-Dong!")
as a standard 16-bit 44.1kHz WAV file at static/bell.wav for reliable playback.
"""

import math
import os
import struct
import wave

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def create_bell_wav(filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    sample_rate = 44100
    duration = 1.6
    num_samples = int(sample_rate * duration)

    # Two-chime reception bell:
    # Strike 1 at t=0.0s: E6 (1318.5 Hz) + overtone
    # Strike 2 at t=0.35s: C6 (1046.5 Hz) + overtone
    # Strike 3 at t=0.70s: G6 (1567.98 Hz) + overtone
    strikes = [
        (0.00, 1046.50, 2093.00),
        (0.28, 1318.51, 2637.02),
        (0.56, 1567.98, 3135.96),
    ]

    with wave.open(filepath, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            sample_val = 0.0
            for start_t, f1, f2 in strikes:
                if t >= start_t:
                    dt = t - start_t
                    env = math.exp(-dt * 4.2)
                    tone = 0.72 * math.sin(2.0 * math.pi * f1 * dt) + 0.28 * math.sin(2.0 * math.pi * f2 * dt)
                    sample_val += env * tone

            # Soft clip & maximize loudness
            sample_val = max(-0.98, min(0.98, sample_val * 0.85))
            int_val = int(sample_val * 32767)
            frames.extend(struct.pack("<h", int_val))

        wav_file.writeframes(bytes(frames))
    print(f"Generated bell sound: {filepath}")


if __name__ == "__main__":
    create_bell_wav(os.path.join(STATIC_DIR, "bell.wav"))
