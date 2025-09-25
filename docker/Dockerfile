# Use an official Python runtime as a parent image
FROM continuumio/miniconda3

RUN apt-get --allow-releaseinfo-change update
RUN apt-get install -y build-essential 

RUN mkdir /tmp/dreutils
COPY ./ /tmp/dreutils/
RUN pip install /tmp/dreutils

RUN rm -rf /tmp/dreutils

ENTRYPOINT ["/opt/conda/bin/dreutilscmd.py"]

CMD ["--help"]
