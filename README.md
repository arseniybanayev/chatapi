# Python Chat API

If your Python application needs chat functionality, then use Python Chat API to easily add it, along with many other features from WhatsApp or Telegram or your favorite messaging app.

Python Chat API works by creating a rich object model on top of any chat server and presenting intuitive behaviors in a modern async paradigm.

The recommended chat server is the awesome open-source [Tinode chat server](https://github.com/tinode/chat). Read more below.

## Why Tinode?

> The promise of XMPP was to deliver federated instant messaging: anyone would be able to spin up an IM server capable of exchanging messages with any other XMPP server in the world. Unfortunately, XMPP never delivered on this promise. Instant messengers are still a bunch of incompatible walled gardens, similar to what AoL of the late 1990s was to the open Internet.
> 
> The goal of this project is to deliver on XMPP's original vision: create a modern open platform for federated instant messaging with an emphasis on mobile communication. A secondary goal is to create a decentralized IM platform that is much harder to track and block by the governments.

## Getting Started

This guide explains how to run the Tinode chat server using Docker and how to use the Python Chat API to connect to it. The guide assumes a Linux environment.

### Prerequisites

1. [Docker](https://docs.docker.com/get-docker/) >= 1.8 because [Docker networking](https://docs.docker.com/network/) may not work with earlier versions
2. Python >= 3.4 because this project uses [asyncio](https://docs.python.org/3/library/asyncio.html) for [cooperative multitasking](https://en.wikipedia.org/wiki/Cooperative_multitasking), as should you

Create a [Docker bridge network](https://docs.docker.com/network/bridge/) for the backing store and the chat server:
```bash
docker network create chat
```

### Installing the backing store for Tinode

We'll use [MySQL](https://www.mysql.com/why-mysql/) for this example. Run the official MySQL container:

```bash
docker run --name mysql --network tinode-net --restart always --env MYSQL_ALLOW_EMPTY_PASSWORD=yes -d mysql:5.7
```

Version >= 5.7 is required. See MySQL Docker instructions for more options. See [deployment notes](#Deployment) for more on running this in production or deploying to a Docker Swarm cluster.

RethinkDB and MongoDB are also supported by the Tinode chat server, and there is ongoing development on a common SQL adapter to support, e.g., PostgreSQL.

### Running the Tinode chat server

Run the Tinode container that corresponds to our choice of MySQL for the backing store:

```bash
docker run -p 6060:6060 -d --name tinode-server --network chat tinode/tinode-mysql:latest
```

See [Tinode documentation](https://github.com/tinode/chat/tree/master/docker) for more on deploying the Tinode chat server using Docker.

### Using Python Chat API

Install Python Chat API into your environment using pip:

```bash
pip install chatapi
```

If you are using Python >= 3.6 then open IPython >= 7.0 because it [supports running asynchronous code from the REPL](https://ipython.readthedocs.io/en/stable/interactive/autoawait.html):

```ipython
In [1]: import chat

In [2]: session = chat.connect('tinode-server', 16060)

In [3]: await session.register('arseniy:mypassword')
Out[3]: 'X6hi1OA2QX71AN5eFAABAAEAgBjSnm1LU/EtSwFyE5Zx1t0b/o9K9nPt5jL3ao/3F8A='

In [4]: topic_name = await session.new_topic()

In [5]: await session.publish_str(topic_name, 'Hello, world!')
```

## Running the tests

Explain how to run the automated tests for this system

### Break down into end to end tests

Explain what these tests test and why

```
Give an example
```

### And coding style tests

Explain what these tests test and why

```
Give an example
```

## <a name="Deployment"></a>Deployment

For serious projects, you might reconsider running the backing store in a container: managed database providers remove the hassle of upgrading, patching, backups and other maintenance, and you can concern yourself less with availability and more with application features.

### Deploying to a Docker Swarm cluster

Bridge networks are not supported on a Swarm cluster, so you would need to create a [Docker overlay network](https://docs.docker.com/network/overlay/) instead:

```bash
docker network create --driver overlay chat
```

If you choose to run MySQL in a container on the Swarm cluster, then you may want to modify the instructions in this guide to run the MySQL container like this:

```bash
docker run --name mysql --network tinode-net --restart always --env MYSQL_ALLOW_EMPTY_PASSWORD=yes --env MYSQL_ROOT_HOST=% -d mysql:5.7 mysqld --bind-address=0.0.0.0
```

The `MYSQL_ROOT_HOST=%` environment variable allows the `root` user to log in from anywhere (like another container's virtual IP address in the Swarm cluster). The `mysqld --bind-address=0.0.0.0` command starts the MySQL server daemon and tells it to listen on all IP addresses on the local host (and all virtual IP addresses of the container).

### Scaling the Tinode chat server

See [Tinode documentation](https://github.com/tinode/chat/blob/master/INSTALL.md#running-a-cluster) for more on scaling. This would need to be adapted for Docker Swarm.

## Built With

* [Dropwizard](http://www.dropwizard.io/1.0.2/docs/) - The web framework used
* [Maven](https://maven.apache.org/) - Dependency Management
* [ROME](https://rometools.github.io/rome/) - Used to generate RSS Feeds

## Contributing

Please read [CONTRIBUTING.md](https://gist.github.com/PurpleBooth/b24679402957c63ec426) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/your/project/tags). 

## Authors

* **Billie Thompson** - *Initial work* - [PurpleBooth](https://github.com/PurpleBooth)

See also the list of [contributors](https://github.com/your/project/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Hat tip to anyone whose code was used
* Inspiration
* etc
