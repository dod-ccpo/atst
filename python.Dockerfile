# syntax=docker/dockerfile:experimental

# Image source is provided using `--build-arg IMAGE=<some-image>`.
# https://docs.docker.com/engine/reference/commandline/build/#options
ARG IMAGE

FROM $IMAGE

# Uses BuildKit preferred method of supplying secrets. These secrets will not
# be saved in the docker image.
#
# https://docs.docker.com/develop/develop-images/build_enhancements/#new-docker-build-secret-information
ARG redhat_username
ARG redhat_password

    # Removes the specified packages from the system along with any
    # packages depending on the packages being removed.
    # https://man7.org/linux/man-pages/man8/yum.8.html
RUN  yum remove python3 && \
    # Removes all “leaf” packages from the system that were originally
    # installed as dependencies of user-installed packages, but which
    # are no longer required by any such package.
    # https://man7.org/linux/man-pages/man8/yum.8.html
    yum autoremove python3 && \
    # Update package repository information.
    # http://man7.org/linux/man-pages/man8/yum.8.html
    yum updateinfo && \
    # Upgrade all packages with their latest security updates.
    # http://man7.org/linux/man-pages/man8/yum.8.html
    yum upgrade --security -y && \
    # Necessary for building python.
    yum install -y gcc libffi-devel make wget zlib-devel && \
    # Causes python to be built with SSL capabilitiy, allowing pip to function.
    yum install -y openssl-devel && \
    # Register this machine with a RedHat subscription.
    # Enables us to add the CodeReady repository.
    subscription-manager remove --all && \
    subscription-manager clean && \
    subscription-manager register \
        --username $redhat_username \
        --password $redhat_password && \
    subscription-manager refresh && \
    subscription-manager attach --auto && \
    # Enable the CodeReady repository.
    # Allows us to install the xmlsec1-devel package.
    # https://access.redhat.com/articles/4348511#enable
    subscription-manager repos --enable codeready-builder-for-rhel-8-x86_64-rpms && \
    # Install dependencies of python3-saml.
    yum install -y libxml2-devel xmlsec1 xmlsec1-openssl libtool-ltdl-devel xmlsec1-devel && \
    # Enable python3 to be built with sqlite extensions.
    yum install -y sqlite sqlite-devel && \
    # Install python!
    # https://github.com/python/cpython#build-instructions
    cd /usr/src && \
    wget https://www.python.org/ftp/python/3.8.7/Python-3.8.7.tgz && \
    tar xzf Python-3.8.7.tgz && \
    cd Python-3.8.7 && \
    ./configure --enable-loadable-sqlite-extensions --enable-optimizations && \
    make install && \
    rm /usr/src/Python-3.8.7.tgz
