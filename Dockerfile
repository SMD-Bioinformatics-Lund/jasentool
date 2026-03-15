# Stage 1: build
FROM python:3.11 AS build-stage

WORKDIR /usr/src/app
COPY . .

RUN apt-get update && \
    apt-get install -y gcc make && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install .

# Stage 2: final image
FROM python:3.11

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        tzdata && \
    ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build-stage /usr/local/bin/jasentool /usr/local/bin/jasentool
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

LABEL authors="Ryan Kennedy <ryan.kennedy@skane.se>" \
      description="Docker image for jasentool"

CMD ["python"]
