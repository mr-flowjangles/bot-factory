#!/bin/bash
exec python3 -c "
from dev_server import app
app.run(host='0.0.0.0', port=8080)
"
