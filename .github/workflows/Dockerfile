FROM python:3.9-slim
MAINTAINER rasper

USER root
WORKDIR /root/

RUN dpkg --add-architecture i386

# Update system
RUN apt-get update && apt-get upgrade --assume-yes --quiet=2
RUN apt-get install --assume-yes --no-install-recommends --no-show-upgraded \
    wget \
    unzip

# Download and uncompress StarCraftII from https://github.com/Blizzard/s2client-proto#linux-packages and remove zip file
RUN wget -q 'http://blzdistsc2-a.akamaihd.net/Linux/SC2.4.10.zip' \
    && unzip -P iagreetotheeula SC2.4.10.zip \
    && rm SC2.4.10.zip

# Install common software via APT
RUN apt-get install --assume-yes --no-install-recommends --no-show-upgraded \
    git  \
    make \
    gcc \
    tree \
    gpg \
    python-dev \
    procps \
    lsof \
    apt-transport-https \
    libgtk2.0-dev \
    software-properties-common \
    dirmngr \
    gpg-agent \
    g++

# Update APT cache
RUN apt-get update

# Upgrade pip and install pip-install requirements
RUN python3 -m pip install --upgrade pip pipenv

# Create a symlink for the maps directory
RUN ln -s /root/StarCraftII/Maps /root/StarCraftII/maps

ADD . /root/queens-sc2

# work around to create the directories required
WORKDIR /root/queens-sc2/queens_sc2
# then to the actual working directory
WORKDIR /root/queens-sc2

COPY queens_sc2/ queens_sc2/

RUN mv .github/workflows/maps/* ~/StarCraftII/maps

RUN python -m pip install -r .github/workflows/docker-requirements.txt

ENTRYPOINT [ "/bin/bash" ]
