TOOL=/home/evgeny/sandbox/cocaine-framework-python/scripts/cocaine-tool
EXAMPLE_PATH=/home/evgeny/sandbox/cocaine-framework-python/examples/echo
tar -czf ${EXAMPLE_PATH}/echo.tar.gz ${EXAMPLE_PATH}/echo.py
${TOOL} app upload --name Echo --manifest=${EXAMPLE_PATH}/manifest.json --package=${EXAMPLE_PATH}/echo.tar.gz
${TOOL} profile upload --name default_echo --profile=${EXAMPLE_PATH}/profile.json