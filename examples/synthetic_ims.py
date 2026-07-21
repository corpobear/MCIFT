# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Generate IMS-shaped synthetic data without downloading or vendoring IMS."""

import numpy as np

from mcift import MCIFTMonitor
from mcift.adapters.ims import adapt_ims_array
from mcift.profiles import VIBRATION_PROFILE_ID

sampling_rate_hz = 20_000.0
samples = 2_048
time = np.arange(samples) / sampling_rate_hz
rng = np.random.default_rng(2026)

reference = []
for _ in range(8):
    values = np.column_stack(
        [
            np.sin(2.0 * np.pi * frequency * time) + rng.normal(0.0, 0.01, samples)
            for frequency in (500.0, 650.0, 800.0, 950.0)
        ]
    )
    reference.append(
        adapt_ims_array(
            values,
            expected_channel_count=4,
            sampling_rate_hz=sampling_rate_hz,
        ).values
    )

monitor = MCIFTMonitor.fit(
    np.asarray(reference),
    sampling_rate_hz=sampling_rate_hz,
    channel_names=["bearing_1", "bearing_2", "bearing_3", "bearing_4"],
    channel_units=["acceleration"] * 4,
    profile=VIBRATION_PROFILE_ID,
)
print(monitor.processing_profile)
