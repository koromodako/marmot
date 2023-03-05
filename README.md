# marmot

## Introduction

This project is at an early stage of testing, security issues and bugs might be
lurking in the corners, use with caution.


## Usage

### marmot-config

Marmot configuration app makes it easy to configure a marmot client
(listener or whistler) or server.

For marmot clients (listeners and whistlers):

- `init-client` makes it possible to initialize the client configuration. Follow
  terminal prompts to perform initialization or use `--use-defaults` option to
  skip the interactive process.
- `show-client` loads the client configuration and prints it in the terminal.

For marmot server everything else is applicable.

- `init-server` makes it possible to initialize the server configuration the
  same way as `init-client` for the client.
- `show-server` loads the server configuration and prints it in the terminal.
- `add-client` registers a client in the server configuration. Clients must be
  registered before being authorized to listen or whistle using `add-listener`
  and `add-whistler`.
- `del-client` unregisters a client in the server configuration.
- `add-channel` creates a channel in the server. Channel must be created before
  adding listeners and whistlers to it.
- `del-channel` deletes a channel in the server.
- `add-whistler` authorize a client to whistle in a channel.
- `del-whistler` client will not be authorized to whistle in given channel until
  reauthorized.
- `add-listener` authorize a client to listen to a channel.
- `del-listener` client will not be authorized to listen in given channel until
  reauthorized.

Marmot server makes it possible to change some of its configuration at runtime.

- `diff` shows differences between persistent configuration values and volatile
  configuration values.
- `push` applies changes made in the persistent configuration in the volatile
  configuration.
- `pull` revert changes made to the persistent configuration by pulling values
  from volatile configuration and overwriting persistent configuration values.

These three commands allow the administrator to add or delete clients, channels,
listeners and whistlers without having to restart the server.


### marmot-listen

Marmot listener can listen to several channels to receive notifications from
whistlers.

`--exec` argument allow forward message properties to an external executable
using an interface based on environment variables. An example of such executable
is `example/script.sh`. File permissions shall allow the user running `marmot-listen`
to execute the file.


### marmot-whistle

Marmot whistlers can whistle to a specific channel to send notifications to
listeners.

Message content is processed as text, you can send base64-encoded binary data,
JSON-encoded structures or anything you want as long as it is text it doesn't
matter.

Message level can be used to indicate the importance of the message, there are
five harcoded levels CRITICAL, ERROR, WARNING, INFO and DEBUG.


### marmot-server

Marmot server needs channels and authorized clients (listeners and whistlers)
to forward messages between clients.  It uses Redis Streams to keep a log of
messages to distribute to channel listeners. It also uses Redis to store parts
of its configuration that the administrator can update without having to restart
the server. This can be achieved pretty easily using `marmot-config` command.


## Setup

### Client 

| Step | Description |
|:----:|:------------|
| `01` | Create a virtual environment: `python3 -m venv venv` |
| `02` | Activate virtual environment: `source venv/bin/activate` |
| `03` | Setup marmot pakage: `python -m pip install git+https://github.com/koromodako/marmot` |
| `04` | Initialize client configuration: `marmot-config init-client` |
| `05` | Retrieve client information: `marmot-config show-client` |
| `06` | Give your GUID and Public Key to the marmot server administrator |
| `07` | The administrator will assign permissions so that you can `marmot-listen` or `marmot-whistle` |


### Server

This documentation does not cover production-ready and secure deployments. It
assumes best practices are followed regarding Nginx and Redis servers deployment.


#### Docker setup

Docker setup is not covered here.

| Step | Description |
|:----:|:------------|
| `01`  | Clone this repository: `git clone https://github.com/koromodako/marmot` |
| `02`  | Create a virtual environment: `python3 -m venv venv` |
| `03`  | Activate virtual environment: `source venv/bin/activate` |
| `04`  | Setup build packages: `python -m pip install build` |
| `05`  | Build marmot package: `python -m build` |
| `06`  | Move to marmot docker directory: `cd docker/marmot` |
| `07`  | Build docker image: `./build.sh` |
| `08`  | Move up to docker directory: `cd ..` |
| `09`  | Start docker deployment: `sudo docker compose up` |
| `10`  | Configure the server: `sudo docker compose exec marmot-server /bin/sh` |
| `11`  | Use `marmot-config` inside the container |


#### Native setup

| Step | Description |
|:----:|:------------|
| `01` | Setup `nginx` and ensure the service is started |
| `02` | Instanciate nginx configuration using template `marmot.nginx.conf` |
| `03` | Provide adequate certificates using your own PKI |
| `04` | Restart `nginx` service |
| `05` | Setup `redis-server` and ensure the service is started |
| `06` | Setup the server following the same procedure as client setup |
| `07` | Initialize server configuration: `marmot-config init-server` |
| `08` | Start the server: `marmot-server` |


## Security

Marmot has been designed with security in mind and ensures some basic principles:

* A client (listener or whistler) can connect if and only if it is explicitly
  declared in server clients list
* A listener can listen to a channel if and only if explicitly declared in this
  channel listeners list
* A whistler can whistle in a channel if and only if explicitly declared in this
  channel whistlers list

These principles are implemented in Marmot using asymmetric cryptography.

Some important security principles are not guaranteed by Marmot implementation
itself and are delegated to other system components. Here is a list of additional
steps required to prevent eavesdropping, replay and spoofing attacks:

* A marmot server should be the only user of a dedicated Redis database
* A marmot server should only be made be accessible through a SSL capable reverse
  proxy and server private key must be kept secret
* A marmot client (listener or whistler) should always verify the authenticity of
  the server through strict certificate checks (dedicated PKI, certificate pinning
  or public key pinning).
* A marmot client (listener or whistler) possesses a passphrase-protected private
  key, it must be kept secret

If these principles are enforced, it should ensure an acceptable security level
for the overall system.

Be aware that phishing and poisonning attacks can still occur if a marmot
whistler fowards information from an untrusted source to the listeners through
the marmot server.


## Testing

No automated testing for now. Manual testing was performed using Python 3.10.6
on Ubuntu 22.04.2 LTS. Assume all Python versions above 3.9 are supported.


## Coding rules

Code is formatted using [black](https://github.com/psf/black) and
[Pylint](https://pylint.org) is used to ensure most of the code is
[PEP8](https://www.python.org/dev/peps/pep-0008) compliant and error free.
