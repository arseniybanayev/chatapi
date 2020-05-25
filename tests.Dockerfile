# Baesd on the github workflow, choose a base python image
ARG PYTHONVERSION=3.8
FROM python:$PYTHONVERSION-slim

WORKDIR /chatapi

# Install netcat (nc) for waiting for tinode-server in the entrypoint
RUN apt-get update && apt-get install -y netcat

# Install linting and testing tools
RUN python -m pip install --upgrade pip
RUN pip install \
    flake8 \
    pytest \
    pytest-asyncio

# Install requirements
COPY ./requirements.txt /chatapi/
RUN pip install -r requirements.txt

# Copy the code
COPY . /chatapi/

# We'll need to wait for tinode-server to be up via docker-compose
RUN chmod +x /chatapi/tests.entrypoint.sh
ENTRYPOINT ["/chatapi/tests.entrypoint.sh"]

CMD ["pytest"]