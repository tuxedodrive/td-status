# Build

Python standard library only. Run:

    python3 render.py INPUT.json OUTPUT_DIRECTORY

Writes one standalone UTF-8 HTML file per ordered observation. Success renders green/healthy; HTTP failures render red/impaired. Unknown results render red/impaired with explicit uncertainty rather than success. Each snapshot shows its observation timestamp, component scope, and always-visible illustrative help. Responsive text and sizing accommodate narrow and wider screens without external assets.

No live monitoring, timing policy, external dependencies, or support service is implemented.
