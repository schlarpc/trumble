"""
Downloads and compiles the protobuf definition file from the Mumble repository.
Requires protoc to be installed.

Use with:
$ update_protobuf.py > trumble/_messages_pb2.py
"""

import os
import subprocess
import sys
import tempfile

import requests


DOWNLOAD_URL = 'https://raw.githubusercontent.com/mumble-voip/mumble/master/src/Mumble.proto'

response = requests.get(DOWNLOAD_URL)

with tempfile.TemporaryDirectory() as proto_path:
    output_path = os.path.join(proto_path, 'output')
    os.makedirs(output_path)
    proto_file = os.path.join(proto_path, '_messages.proto')
    with open(proto_file, 'wb') as f:
        f.write(response.content)
    args = ['protoc', '--proto_path={}'.format(proto_path), proto_file, '--python_out={}'.format(output_path)]
    subprocess.run(args, stdout=sys.stderr)
    output_file = os.path.join(output_path, '_messages_pb2.py')
    with open(output_file, 'r') as f:
        print(f.read(), end='')
