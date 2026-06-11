FROM continuumio/miniconda3

RUN apt-get --allow-releaseinfo-change update && \
    apt-get install -y --no-install-recommends build-essential ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/aixport
COPY ./ /opt/aixport/
RUN python -m pip install --no-cache-dir /opt/aixport && \
    python -m pip check

COPY .dnanexus/run.sh /opt/aixport/run.sh
RUN chmod a+x /opt/aixport/run.sh

ENTRYPOINT ["/opt/aixport/run.sh"]
CMD ["--help"]
