# Base Image 
FROM fedora:40

# 1. Setup home directory, non interactive shell and timezone
RUN mkdir -p /bot /neon && chmod 777 /bot
WORKDIR /bot
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Africa/Lagos
ENV TERM=xterm

# 2. Install Dependencies
RUN dnf -qq -y update && dnf -qq -y install git bash xz wget curl python3-pip psmisc procps-ng ImageMagick-devel && if [[ $(arch) == 'aarch64' ]]; then   dnf -qq -y install gcc python3-devel; fi && python3 -m pip install --upgrade pip setuptools

# 3. Install latest ffmpeg
RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/64/) && \
    wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux${arch}-gpl-7.1.tar.xz && tar -xvf *xz && cp *7.1/bin/* /usr/bin && rm -rf *xz && rm -rf *7.1

RUN arch=$(arch | sed s/x86_64/x86-64/) && \
    wget -q https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-1.5.0-linux-${arch}.tar.gz && tar -xvf *gz && cp libwebp*/bin/img2webp /usr/bin && cp libwebp*/bin/webpmux /usr/bin && rm -rf *gz && rm -rf libwebp*

# Install postgresql repo & latest postgresql 
RUN if [[ $(arch) == 'x86_64' ]]; then dnf -qq -y install "https://download.postgresql.org/pub/repos/yum/reporpms/F-$(. /etc/os-release; echo $VERSION_ID)-x86_64/pgdg-fedora-repo-latest.noarch.rpm"; fi
RUN if [[ $(arch) == 'x86_64' ]]; then \
        dnf -qq -y install postgresql17-server; \
    else \
        dnf -qq -y install postgresql-server; \
    fi

# 4. Copy files from repo to home directory
COPY . .

# 5. Install python3 requirements
RUN pip3 install -r requirements.txt

# 6. cleanup for arm64
RUN if [[ $(arch) == 'aarch64' ]]; then   dnf -qq -y history undo last; fi && dnf clean all

# 7. Start bot
CMD ["bash","run.sh"]
