FROM ubuntu:precise

RUN apt-get update && apt-get install python-flask msgpack-python python-pip -y
RUN pip install cocaine

ADD ./main.py /
ADD ./app.py /
