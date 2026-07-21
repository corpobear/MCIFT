# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Small offline lifecycle example using synthetic healthy windows."""

import numpy as np

from mcift import MCIFTMonitor

rng = np.random.default_rng(2026)
healthy = rng.normal(size=(10, 128, 3))
calibration = rng.normal(size=(20, 128, 3))

monitor = MCIFTMonitor.fit(
    healthy,
    sampling_rate_hz=1_000.0,
    channel_names=["sensor_a", "sensor_b", "sensor_c"],
    channel_units=["V", "V", "V"],
).calibrate(calibration)

result = monitor.evaluate(calibration[-1])
print(monitor.explain(result))
