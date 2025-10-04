#T41-SDT-Pi
This project is an attempt to reimplement the software stack of the T41-EP SDT, allowing it to run on Linux-based systems such as a Raspberry Pi.

The backend is implemented in Python and controls all interaction with the T41 hardware, including user interface elements (encoders and buttons).

The display layer is implemented as a web application which communicates with the Python backend using a REST and WebRTC.
