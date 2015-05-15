FROM ubuntu:precise

RUN apt-get update && apt-get install python-flask msgpack-python python-pip -y
RUN pip install git+https://github.com/cocaine/cocaine-framework-python

ADD ./main.py /
ADD ./app.py /
