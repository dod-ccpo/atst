FROM cloudzeroopsregistry.azurecr.io/rhel-py:latest

COPY ./azure-cli.repo /etc/yum.repos.d/azure-cli.repo

RUN yum -y update && \
  rpm --import https://packages.microsoft.com/keys/microsoft.asc &&  \
  yum install -y azure-cli bzip2-devel gettext git jq openssl-devel postgresql-devel unzip && \ 
  curl https://releases.hashicorp.com/terraform/0.13.0/terraform_0.13.0_linux_amd64.zip -o tf.zip && \
  unzip tf.zip && \
  sudo mv terraform /usr/local/bin && \
  ln -s /usr/bin/python /usr/bin/python3.7 && \
  cd /tmp && \
  curl --retry 10 -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" && \
  chmod +x /tmp/kubectl && \
  sudo mv /tmp/kubectl /usr/bin/kubectl

COPY ./ops/requirements.txt /src/ops/requirements.txt

RUN pip3 install -r /src/ops/requirements.txt

COPY . /src

WORKDIR /src/ansible

ENTRYPOINT ["../ops/entrypoint.sh"]