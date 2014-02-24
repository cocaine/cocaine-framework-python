FROM ubuntu:precise

RUN echo "deb http://archive.ubuntu.com/ubuntu precise main universe" > /etc/apt/sources.list
RUN apt-get update

RUN apt-get install python-flask msgpack-python python-pip -y
RUN pip install cocaine
