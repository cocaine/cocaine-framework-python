APP_NAME=Chunker
APP_FILENAME=chunker
FRAMEWORK_ROOT_PATH=/home/evgeny/sandbox/cocaine-framework-python
TOOL=${FRAMEWORK_ROOT_PATH}/scripts/cocaine-tool
EXAMPLES_PATH=${FRAMEWORK_ROOT_PATH}/examples/${APP_FILENAME}

chmod u+x ${EXAMPLES_PATH}/${APP_FILENAME}.py
tar -czf ${EXAMPLES_PATH}/${APP_FILENAME}.tar.gz ${EXAMPLES_PATH}/${APP_FILENAME}.py

${TOOL} app upload --name ${APP_NAME} --manifest=${EXAMPLES_PATH}/manifest.json --package=${EXAMPLES_PATH}/${APP_FILENAME}.tar.gz
${TOOL} profile upload --name ${APP_NAME}Profile --profile=${EXAMPLES_PATH}/profile.json
${TOOL} app start --name ${APP_NAME} --profile=${APP_NAME}Profile