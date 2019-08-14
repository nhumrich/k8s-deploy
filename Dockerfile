FROM python:alpine

RUN apk --no-cache add curl
RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

WORKDIR /scripts
COPY requirements.txt /scripts
RUN pip install -r requirements.txt

COPY scripts /scripts/

CMD ["python", "/scripts/k8s-deploy.py"]


    



