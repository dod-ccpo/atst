ARG IMAGE=cloudzeroopsregistry.azurecr.io/rhel-py:latest

FROM $IMAGE

COPY ./azure-cli.repo /etc/yum.repos.d/azure-cli.repo

RUN yum -y update && \
  rpm --import https://packages.microsoft.com/keys/microsoft.asc &&  \
  yum install -y azure-cli bzip2-devel gettext git jq openssl-devel postgresql-devel unzip && \
  curl https://releases.hashicorp.com/terraform/0.13.5/terraform_0.13.5_linux_amd64.zip -o tf.zip && \
  unzip tf.zip && \
  sudo mv terraform /usr/local/bin && \
  ln -s /usr/local/bin/python3.8 /usr/local/bin/python \
  cd /tmp && \
  curl --retry 10 -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" && \
  chmod +x /tmp/kubectl && \
  sudo mv /tmp/kubectl /usr/bin/kubectl && \
  curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 && \
  chmod 700 get_helm.sh && \
  ./get_helm.sh && \
  yum install -y rsyslog && \
  curl -s https://raw.githubusercontent.com/a2o/snoopy/install/install/install-snoopy.sh -o /tmp/install-snoopy.sh && \
  chmod +x /tmp/install-snoopy.sh && \
  /tmp/install-snoopy.sh stable && \
  snoopy-enable && \
  yum clean all

COPY ./ops/requirements.txt /src/ops/requirements.txt

COPY ./ops/files/snoopy.ini /etc/snoopy.ini

RUN chmod +x /etc/snoopy.ini && touch /var/log/snoopy.log

RUN pip3 install -r /src/ops/requirements.txt

WORKDIR /src

COPY . /src

WORKDIR /src/ops/phase2

ENTRYPOINT "/bin/bash"

CMD ["tail","-f","/var/log/snoopy.log"]