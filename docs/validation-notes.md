# Validation Notes

## Initial Validation Areas
Useful first checks include:

1. Every line endpoint references a valid node.
2. Every switch or device references valid nodes.
3. Equipment IDs are unique where they should be unique.
4. The expected feeder or source exists.
5. Required ratings and impedance values are populated.
6. Loads are attached to valid buses or nodes.
7. The feeder does not contain unexpected disconnected islands.
8. Counts of major equipment types match expected Synergi or model counts.

## Schema Notes
Synergi export schemas may vary between versions and export settings. Validation logic should be written against the actual observed MDB schema, not assumptions about a fixed export layout.
