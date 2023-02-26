"""EventSource
"""
import typing as t
from dataclasses import dataclass


@dataclass
class Event:
    """Event"""
    id_: t.Optional[bytes] = None
    event: t.Optional[bytes] = None
    data: bytes = b''
    retry: t.Optional[int] = None


def parse_event(event_lines):
    """Parse a server-side event"""
    event = Event()
    for line in event_lines:
        if line.startswith(b'id:'):
            event.id_ = line.split(b': ', 1)[-1]
        if line.startswith(b'event:'):
            event.event = line.split(b': ', 1)[-1]
        if line.startswith(b'data:'):
            event.data += line.split(b': ', 1)[-1]
        if line.startswith(b'retry:'):
            event.retry = int(line.split(b': ', 1)[-1].decode())
    return event


async def event_source_stream(resp):
    """Yield events from event source stream"""
    event_lines = []
    while True:
        line = (await resp.content.readline()).rstrip()
        if line:
            if line.startswith(b':'):
                continue
            event_lines.append(line)
            continue
        # if event buffer is not empty, parse event
        if event_lines:
            yield parse_event(event_lines)
        # reset event buffer
        event_lines.clear()
