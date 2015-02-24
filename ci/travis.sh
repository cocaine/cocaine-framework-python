#!/bin/sh

install_utility () {
    sudo apt-get update -qq && sudo apt-get install -qq devscripts build-essential equivs python-software-properties
}

build_cocaine () {
  git clone --recursive https://github.com/cocaine/cocaine-core.git -b master
  cd cocaine-core
  yes | sudo mk-build-deps -i
  yes | debuild -uc -us
  cd .. && sudo dpkg -i *.deb || sudo apt-get install -f && rm -rf cocaine-core 
}

make_env () {
    echo "Install utility packages..."
    install_utility
    echo "Build & install packages..."
    build_cocaine
    echo "Waiting..."
    sleep 5
}

make_env
