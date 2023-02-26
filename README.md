# marmot

## Usage

### Listener

Marmot listener can listen to a specific channel to receive notifications from
whistlers.

TODO


### Whistler

Marmot whistlers can whistle to a specific channel to send notifications to
listeners.

TODO


### Server

Marmot server need to create channels, authorize listeners and whistlers to
connect and authorize listeners and whistlers participation in individual
channels. This can be achieved pretty easily using `marmot-config` command.

TODO


## Setup

### Client 

1. Create a virtual environment: `python3 -m venv venv`
2. Activate virtual environment: `source venv/bin/activate`
3. Setup marmot pakage: `python -m pip install git+https://github.com/koromodako/marmot`
4. Initialize client configuration: `marmot-config -c marmot-client.json init-client`


### Server

1. Setup `nginx` and ensure the service is started
2. Instanciate nginx configuration using template `marmot.nginx.conf`
3. Provide adequate certificates using your own PKI
4. Restart `nginx` service
5. Setup `redis-server` and ensure the service is started
6. Setup the server following the same procedure as client setup
7. Initialize server configuration: `marmot-config -c marmot-server.json init-server`
8. Start the server: `marmot-server -c marmot-server.json`

Server can be *dockerized* or configured as a `systemd` service.


## Security

Marmot has been designed with security in mind and ensures some basic principles:

* A client (listener or whistler) can connect if and only if it is explicitly
  declared in server clients list
* A listener can listen to a channel if and only if explicitly declared in this
  channel listeners list
* A whistler can whistle in a channel if and only if explicitly declared in this
  channel whistlers list

These principles are implemented in Marmot using asymmetric cryptography and signing.

Some necessary security properties are not guaranteed by Marmot implementation
itself and are delegated to other system components. Here is a list of additional
steps required to prevent eavesdropping, replay and spoofing attacks:

* A marmot server should be the only authorized user of the required redis server
* A marmot server should only be made be accessible through a SSL capable reverse
  proxy and server private key must be kept secret
* A marmot client (listener or whistler) should always verify the authenticity of
  the server through strict certificate checks
* A marmot client (listener or whistler) possesses a passphrase-protected private
  key, it must be kept secret

If these rules are enforced, it should ensure an acceptable security level for
the overall system.

Be aware that phishing and poisonning attacks can still occur if a marmot whistler
fowards information from an untrusted source to the marmot server.


## Documentation

There is no documentation other than this README for now but most of the code is 
documented.


## Testing

There is no automated testing for now. Manual testing was performed using
Python 3.9.7 on Ubuntu 21.10. Assume all Python versions above 3.9 are supported.


## Coding rules

Code is formatted using [black](https://github.com/psf/black) and
[Pylint](https://pylint.org) is used to ensure most of the code is
[PEP8](https://www.python.org/dev/peps/pep-0008) compliant and error free.
