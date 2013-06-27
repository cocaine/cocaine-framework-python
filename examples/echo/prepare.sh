FRAMEWORK_ROOT_PATH=~/sandbox/cocaine-framework-python

TOOL=${FRAMEWORK_ROOT_PATH}/scripts/cocaine-tool
EXAMPLES_PATH=${FRAMEWORK_ROOT_PATH}/examples/echo

chmod u+x ${EXAMPLES_PATH}/echo.py
tar -czf ${EXAMPLES_PATH}/echo.tar.gz ${EXAMPLES_PATH}/echo.py

${TOOL} app upload --name Echo --manifest=${EXAMPLES_PATH}/manifest.json --package=${EXAMPLES_PATH}/echo.tar.gz
${TOOL} profile upload --name EchoProfile --profile=${EXAMPLES_PATH}/profile.json
${TOOL} app start --name Echo --profile=EchoProfile
