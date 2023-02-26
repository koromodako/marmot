# marmot

## Usage

### Publisher

TODO

### Subscriber

TODO

## Setup

### Client 

Setup is almost the same for Linux, Darwin and Windows.

```bash
# assuming 'python' is python 3 executable
python -m venv venv
source venv/bin/activate
pip install git+https://github.com/koromodako/marmot
```

### Server

TODO

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
