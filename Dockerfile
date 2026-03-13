# Stage 1: build
FROM python:3.11 AS build-stage

WORKDIR /usr/src/app
COPY . .

RUN apt-get update && \
    apt-get install -y gcc make wget xz-utils apt-utils && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install .

# Download and install Sambamba
RUN wget https://github.com/biod/sambamba/releases/download/v1.0.1/sambamba-1.0.1-linux-amd64-static.gz && \
    gunzip sambamba-1.0.1-linux-amd64-static.gz && \
    chmod +x sambamba-1.0.1-linux-amd64-static && \
    mv sambamba-1.0.1-linux-amd64-static /usr/bin/sambamba

# Download Picard
RUN wget https://github.com/broadinstitute/picard/releases/download/3.1.1/picard.jar && \
    chmod +x picard.jar && \
    mv picard.jar /usr/bin/picard.jar

# Stage 2: final image
FROM python:3.11

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        tzdata && \
    ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build-stage /usr/bin/sambamba /usr/bin/sambamba
COPY --from=build-stage /usr/bin/picard.jar /usr/bin/picard.jar
COPY --from=build-stage /usr/local/bin/jasentool /usr/local/bin/jasentool
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

RUN echo 'alias picard="java -jar /usr/bin/picard.jar"' >> ~/.bashrc

LABEL authors="Ryan Kennedy <ryan.kennedy@skane.se>" \
      description="Docker image for jasentool"

CMD ["python"]
