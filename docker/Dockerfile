# Use an official Python runtime as a parent image
FROM continuumio/miniconda3

RUN apt-get --allow-releaseinfo-change update
RUN apt-get install -y build-essential 

RUN mkdir /tmp/aixport
COPY ./ /tmp/aixport/
RUN pip install /tmp/aixport

RUN rm -rf /tmp/aixport

ENTRYPOINT ["/opt/conda/bin/aixportcmd.py"]

CMD ["--help"]
