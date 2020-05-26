# Python Chat API

![Build and Test](https://github.com/arseniybanayev/chatapi/workflows/Build%20and%20Test/badge.svg)

If your Python application needs chat functionality, then use Python Chat API to easily add it, along with many other features from WhatsApp or Telegram or your favorite messaging app.

Python Chat API works by creating a rich object model on top of any chat server and presenting intuitive behaviors in a modern async paradigm.

The recommended chat server is the awesome open-source [Tinode chat server](https://github.com/tinode/chat). Read more below.

## Why Tinode?

> The promise of XMPP was to deliver federated instant messaging: anyone would be able to spin up an IM server capable of exchanging messages with any other XMPP server in the world. Unfortunately, XMPP never delivered on this promise. Instant messengers are still a bunch of incompatible walled gardens, similar to what AoL of the late 1990s was to the open Internet.
> 
> The goal of this project is to deliver on XMPP's original vision: create a modern open platform for federated instant messaging with an emphasis on mobile communication. A secondary goal is to create a decentralized IM platform that is much harder to track and block by the governments.

## <a name="GettingStarted"></a>Getting Started

This guide explains how to run the Tinode chat server using Docker and how to use the Python Chat API to connect to it. The guide assumes a Linux environment.

### Prerequisites

1. [Docker](https://docs.docker.com/get-docker/) >= 1.8 because [Docker networking](https://docs.docker.com/network/) may not work with earlier versions
2. Python >= 3.6 because this project uses [asyncio](https://docs.python.org/3/library/asyncio.html) for [cooperative multitasking](https://en.wikipedia.org/wiki/Cooperative_multitasking), as should you

Create a [Docker bridge network](https://docs.docker.com/network/bridge/) for the backing store and the chat server:
```bash
$ docker network create chat
```

### Installing the backing store for Tinode

We'll use [MySQL](https://www.mysql.com/why-mysql/) for this example. Run the official MySQL container:

```sh
$ docker run \
    --name mysql \
    --network chat \
    --restart always \
    --env MYSQL_ALLOW_EMPTY_PASSWORD=yes \
    -d \
    mysql:5.7
```

Version >= 5.7 is required. See MySQL Docker instructions for more options. See [deployment notes](#Deployment) for more on running this in production or deploying to a Docker Swarm cluster.

RethinkDB and MongoDB are also supported by the Tinode chat server, and there is ongoing development on a common SQL adapter to support, e.g., PostgreSQL.

### Running the Tinode chat server

Run the Tinode container that corresponds to our choice of MySQL for the backing store, exposing port 16060 for the gRPC channel.

```bash
$ docker run \
    --name tinode-server \
    --network chat \
    -p 16060:16060 \
    -d \
    tinode/tinode-mysql:latest
```

See [Tinode documentation](https://github.com/tinode/chat/tree/master/docker) for more on deploying the Tinode chat server using Docker.

### Using Python Chat API

Install Python Chat API into your environment using pip:

```
$ pip install chatapi
```

The following example registers a new user, creates a new group topic and sends a `"Hello, world!"` message.

```python
import chat
session = chat.quick_connect('tinode-server', 16060)
token = await session.register('arseniy:mypassword')
topic_name = await session.new_topic()
await session.publish_str(topic_name, 'Hello, world!')
```

For more examples, see the [documentation]().

## <a name="Deployment"></a>Deployment

For serious projects, you might reconsider running the backing store in a container: managed database providers remove the hassle of upgrading, patching, backups and other maintenance, and you can concern yourself less with availability and more with application features.

### Deploying to a Docker Swarm cluster

Bridge networks are not supported on a Swarm cluster, so you would need to create a [Docker overlay network](https://docs.docker.com/network/overlay/) instead:

```bash
$ docker network create --driver overlay chat
```

If you choose to run MySQL in a container on the Swarm cluster, then you may want to modify the instructions in this guide to run the MySQL container like this:

```bash
$ docker run \
    --name mysql \
    --network tinode-net \
    --restart always \
    --env MYSQL_ALLOW_EMPTY_PASSWORD=yes \
    --env MYSQL_ROOT_HOST=% \
    -d \
    mysql:5.7 \
    mysqld --bind-address=0.0.0.0
```

The `MYSQL_ROOT_HOST=%` environment variable allows the `root` user to log in from anywhere (like another container's virtual IP address in the Swarm cluster). The `mysqld --bind-address=0.0.0.0` command starts the MySQL server daemon and tells it to listen on all IP addresses on the local host (and all virtual IP addresses of the container).

### Scaling the Tinode chat server

See [Tinode documentation](https://github.com/tinode/chat/blob/master/INSTALL.md#running-a-cluster) for more on scaling. This would need to be adapted for Docker Swarm.

## Testing

If you have the ports exposed properly after following the [Getting started](#GettingStarted) guide above, then you can do:

```bash
$ pip install pytest-asyncio
$ export CHAT_HOST=tinode-server
$ export CHAT_HOST=16060
$ pytest
```

### Testing with docker-compose

Tests are easily run via [docker-compose](https://docs.docker.com/compose/). The [build-and-test](.github/workflows/build-and-test.yml) workflow runs automatically on GitHub and does everything mentioned below.

First, set the environment variable `GITHUB_RUN_ID` to something on your local machine. (This is automatically set to a unique run ID in the GitHub workflow.)

```bash
$ export GITHUB_RUN_ID=my_test_run
```

Then, build the testing image with the expected tag. (The PYTHONVERSION build arg defaults to `3.8`, but it is set to all of `[3.6, 3.7, 3.8]` in the GitHub workflow.)

```bash
$ docker build \
    -t chatapi-tests-$GITHUB_RUN_ID \
    --build-arg PYTHONVERSION=3.7 \
    -f tests.Dockerfile \
    .
```

The `tests.docker-compose.yml` file starts a MySQL container, a Tinode chat server container and a Python Chat API testing container, which automatically runs `pytest` when the backing store and chat server are ready. The GitHub workflow does this after building the testing image:

```bash
$ docker-compose \
    -f tests.docker-compose.yml \
    up \
    --abort-on-container-exit \
    --exit-code-from pytest
```

### Linting

The testing image contains `flake8` which is used by the GitHub workflow. You can lint with:

```
$ docker run chatapi-tests-$GITHUB_RUN_ID flake8 .
```

You can also lint in your own environment with:

```bash
$ pip install flake8
$ flake8 .
```

## Versioning

This project uses [semantic versioning](http://semver.org/) for versioning.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## Acknowledgments

* [or-else (Gene)](https://github.com/or-else) for Tinode chat server
