# Architecture

The stable package follows an immutable `fit -> calibrate -> evaluate -> explain ->
save/load` lifecycle. Versioned processing profiles freeze preprocessing and threshold
conventions. Reference fitting freezes scales and healthy relationships. Calibration
freezes thresholds. Evaluation performs scoring only. Streaming state lives in an
explicit caller-owned `MCIFTHistory` value.

Persistence uses the logical OR of global and local base gates. Directional
corroboration uses only eligible local-positive edges. Gate results report availability
separately from pass/fail. Progression remains unavailable unless calibration was
explicitly chronological.

`mcift.gates.exchange-screening.v1` preserves the five-gate compatibility behavior.
`mcift.gates.ims-six-gate.v1` adds conventional vibration evidence and the frozen
six-gate decision policy documented in SDR-0006.

Experimental modules are isolated below `mcift.experimental`; stable modules do not
import them, and release artifacts exclude that namespace. The core has no runtime
network behavior. Model loading uses verified JSON and non-object NumPy arrays with
pickling disabled.

Synthetic golden fixtures preserve historical telemetry and vibration outputs. The
initial full NASA IMS Test Set 2 run is documented separately. Exathlon execution and
general cross-dataset compatibility remain unestablished.
