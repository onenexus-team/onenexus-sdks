import argparse

from ._version import __version__
from .auth import (
    create_private_key_jwt_credentials,
    load_api_url,
    load_cas_url,
    load_credential_login,
    load_token,
)
from .client import OneNexusClient
from .cli_commands import (
    add_auth_commands,
    add_data_hub_commands,
    add_inference_commands,
    add_model_registry_commands,
    add_tenant_workspace_commands,
    add_training_commands,
)
from .cli_errors import render_error
from .cli_progress import transfer_progress_for
from .cli_render import render_result


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        with transfer_progress_for(args):
            if getattr(args, "auth_command", None):
                result = args.handler(args)
            else:
                token = load_token(args.token)
                credential_login = None if token else load_credential_login()
                if not token and not credential_login:
                    parser.error("run `nexusai login` or pass --token")
                api_url = load_api_url(args.base_url)
                cas_url = load_cas_url(args.cas_url)
                if token:
                    client = OneNexusClient(
                        token=token,
                        base_url=api_url,
                        cas_url=cas_url,
                    )
                else:
                    assert credential_login is not None
                    client = OneNexusClient.from_credentials(
                        create_private_key_jwt_credentials(
                            credential_login,
                            cas_url=cas_url,
                        ),
                        base_url=api_url,
                        cas_url=cas_url,
                    )
                result = args.handler(client, args)
        if result is not None:
            render_result(
                result,
                output=args.output,
                field=args.field,
                no_color=args.no_color,
            )
    except KeyboardInterrupt as error:
        raise SystemExit(
            render_error(error, no_color=args.no_color, debug=args.debug)
        ) from None
    except Exception as error:
        raise SystemExit(
            render_error(error, no_color=args.no_color, debug=args.debug)
        ) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexusai")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument("--token", help="Token. Overrides saved login token.")
    parser.add_argument(
        "--base-url",
        help="Platform URL. Overrides saved login URL for this command.",
    )
    parser.add_argument(
        "--cas-url",
        help="CAS URL. Overrides saved CAS URL for this command.",
    )
    parser.add_argument(
        "--output",
        choices=("table", "json"),
        default="table",
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--field",
        help="Print one dot-separated field for shell automation.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include a traceback for unexpected CLI failures.",
    )
    domains = parser.add_subparsers(dest="domain", required=True)

    add_auth_commands(domains)
    add_tenant_workspace_commands(domains)
    add_data_hub_commands(domains)
    add_model_registry_commands(domains)
    add_training_commands(domains)
    add_inference_commands(domains)
    return parser
