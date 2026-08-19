# Base Image 
FROM fedora:40

# 1. Setup home directory, non interactive shell and timezone
RUN mkdir -p /bot /neon && chmod 777 /bot
WORKDIR /bot
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Africa/Lagos
ENV TERM=xterm

# 2. Install Dependencies
RUN dnf -qq -y update && dnf -qq -y install git bash xz wget curl mediainfo python3-pip psmisc procps-ng unzip ImageMagick-devel && python3 -m pip install --upgrade pip setuptools

# 3. Install latest ffmpeg & other dependencies
RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/64/) && \
    wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux${arch}-gpl.tar.xz && tar -xvf *xz && cp ffmpeg*gpl/bin/* /usr/bin && rm -rf *xz && rm -rf ffmpeg*

RUN arch=$(arch) && \
    wget -q https://github.com/denoland/deno/releases/download/v2.9.5/deno-${arch}-unknown-linux-gnu.zip && unzip *zip -d out && cp out/deno /usr/bin/ && rm -rf *zip && rm -rf out

RUN arch=$(arch | sed s/x86_64/x86-64/) && \
    wget -q https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-1.5.0-linux-${arch}.tar.gz && tar -xvf *gz && cp libwebp*/bin/img2webp /usr/bin && cp libwebp*/bin/webpmux /usr/bin && rm -rf *gz && rm -rf libwebp*
    
RUN dnf -qq -y update && dnf -qq -y install \
    chromium \
    alsa-lib \
    atk \
    cups-libs \
    gtk3 \
    libXcomposite \
    libXdamage \
    libXrandr \
    libXtst \
    pango \
    xorg-x11-server-Xvfb \
    mesa-libGL \
    ca-certificates \
    python3-tkinter \
    && dnf clean all && useradd -m chromeuser

RUN dnf -qq -y install libicu-devel pkgconf-pkg-config gcc-c++

RUN dnf -qq -y install gcc python3-devel

# 4. Copy files from repo to home directory
COPY . .

# 5. Install python3 requirements
RUN pip3 install -r requirements.txt

# 6. cleanup
RUN dnf -qq -y history undo last && dnf clean all

# 7. Start bot
CMD ["bash","run.sh"]
