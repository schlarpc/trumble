import argparse
import logging

from . import SimpleTrumble

def get_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', type=(lambda x: getattr(logging, x)), default='DEBUG')
    parser.add_argument('--access-token', action='append')
    parser.add_argument('--no-verify', action='store_true', default=False)
    parser.add_argument('host')
    parser.add_argument('port', nargs='?', type=int, default=64738)
    return parser.parse_args()

def main(argv=None):
    args = get_args(argv)
    logging.basicConfig(level=args.log_level)

    trumble = SimpleTrumble(
        args.host,
        args.port,
        verify=not args.no_verify,
        access_tokens=args.access_token,
    )
    trumble.run()

if __name__ == '__main__':
    main()