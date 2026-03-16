"""Download alleles from PubMLST / BIGSdb Pasteur via OAuth1 REST API (Issue #19).

Script to download authenticated resources from PubMLST and BIGSdb Pasteur
via their REST interfaces.
Written by Keith Jolley
Copyright (c) 2024-2025, University of Oxford
E-mail: keith.jolley@biology.ox.ac.uk

BIGSdb_downloader is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
Version 20250225 (ported to jasentool class interface)
"""

import configparser
import json
import os
import re
import stat
import sys
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs

from rauth import OAuth1Service, OAuth1Session

from jasentool.log import get_logger

logger = get_logger(__name__)

BASE_WEB = {
    "PubMLST": "https://pubmlst.org/bigsdb",
    "Pasteur": "https://bigsdb.pasteur.fr/cgi-bin/bigsdb/bigsdb.pl",
}
BASE_API = {
    "PubMLST": "https://rest.pubmlst.org",
    "Pasteur": "https://bigsdb.pasteur.fr/api",
}


class BIGSdb:
    """Authenticate with PubMLST or BIGSdb Pasteur and download scheme alleles."""

    def __init__(self, options):
        self.key_name = options.key_name
        self.token_dir = options.token_dir
        self.site = options.site
        self.url = options.url
        self.db = options.db
        self.setup = options.setup
        self.download_scheme = options.download_scheme
        self.output_dir = options.output_dir
        self.output_file = options.output_file
        self.force = options.force
        self.cron = options.cron
        self.method = options.method

    def run(self):
        """Entry point: validate args, authenticate, then download or call route."""
        self._check_required_args()
        self._check_dir(self.token_dir)
        if self.setup:
            (access_token, access_secret) = self._get_new_access_token()
            if not access_token or not access_secret:
                raise PermissionError("Cannot get new access token.")
        (token, secret) = self._retrieve_token("session")
        if not token or not secret:
            (token, secret) = self._get_new_session_token()
        if self.download_scheme:
            self._download_scheme_alleles(self.url, token, secret, self.output_dir)
        elif not self.setup:
            self._get_route(self.url, token, secret)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _check_required_args(self):
        if not self.key_name:
            logger.error("--key-name is required")
            sys.exit(1)
        if self.download_scheme:
            missing = []
            if not self.url:
                missing.append("--url")
            if not self.output_dir:
                missing.append("--output-dir")
            if not self.site:
                missing.append("--site")
            if missing:
                logger.error("%s required with --download-scheme", ", ".join(missing))
                sys.exit(1)
            return
        if self.setup:
            if not self.site:
                logger.error("--site is required for setup")
                sys.exit(1)
            if not self.db:
                logger.error("--db is required for setup")
                sys.exit(1)
        else:
            if not self.url:
                logger.error("--url is required")
                sys.exit(1)

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_dir(directory):
        if os.path.isdir(directory):
            if not os.access(directory, os.W_OK):
                raise PermissionError(
                    f"Token directory '{directory}' exists but is not writable."
                )
        else:
            try:
                os.makedirs(directory)
                os.chmod(directory, stat.S_IRWXU)
            except OSError as exc:
                raise PermissionError(
                    f"Failed to create token directory '{directory}': {exc}"
                ) from exc

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _retrieve_token(self, token_type):
        file_path = Path(f"{self.token_dir}/{token_type}_tokens")
        if file_path.is_file():
            config = configparser.ConfigParser(interpolation=None)
            config.read(file_path)
            if config.has_section(self.key_name):
                token = config[self.key_name]["token"]
                secret = config[self.key_name]["secret"]
                return (token, secret)
        return (None, None)

    def _get_new_session_token(self):
        file_path = Path(f"{self.token_dir}/session_tokens")
        (access_token, access_secret) = self._retrieve_token("access")
        if not access_token or not access_secret:
            (access_token, access_secret) = self._get_new_access_token()
        (client_key, client_secret) = self._get_client_credentials()
        db = self._get_db_value()
        url = f"{BASE_API[self.site]}/db/{db}/oauth/get_session_token"
        session_request = OAuth1Session(
            client_key,
            client_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        resp = session_request.get(url, headers={"User-Agent": "BIGSdb downloader"})
        if resp.status_code == 200:
            token = resp.json()["oauth_token"]
            secret = resp.json()["oauth_token_secret"]
            config = configparser.ConfigParser(interpolation=None)
            if file_path.is_file():
                config.read(file_path)
            config[self.key_name] = {"token": token, "secret": secret}
            with open(file_path, "w", encoding="utf-8") as configfile:
                config.write(configfile)
            return (token, secret)

        msg = resp.json().get("message", "")
        sys.stderr.write(f"Failed to get new session token. {msg}\n")
        if self.cron:
            sys.stderr.write("Run interactively to fix.\n")
        if re.search("verification", msg) or re.search("Invalid access token", msg):
            sys.stderr.write("New access token required - removing old one.\n")
            config = configparser.ConfigParser(interpolation=None)
            access_path = Path(f"{self.token_dir}/access_tokens")
            if access_path.is_file():
                config.read(access_path)
                config.remove_section(self.key_name)
                with open(access_path, "w", encoding="utf-8") as configfile:
                    config.write(configfile)
        sys.exit(1)

    def _get_service(self):
        (client_key, client_secret) = self._get_client_credentials()
        db = self._get_db_value()
        request_token_url = f"{BASE_API[self.site]}/db/{db}/oauth/get_request_token"
        access_token_url = f"{BASE_API[self.site]}/db/{db}/oauth/get_access_token"
        return OAuth1Service(
            name="BIGSdb_downloader",
            consumer_key=client_key,
            consumer_secret=client_secret,
            request_token_url=request_token_url,
            access_token_url=access_token_url,
            base_url=BASE_API[self.site],
        )

    def _get_new_access_token(self):
        if self.cron:
            sys.stderr.write(f"No access token saved for {self.key_name}.\n")
            sys.stderr.write("Run interactively to set.\n")
            sys.exit(1)
        file_path = Path(f"{self.token_dir}/access_tokens")
        (request_token, request_secret) = self._get_new_request_token()
        db = self._get_db_value()
        print(
            "Please log in using your user account at "
            f"{BASE_WEB[self.site]}?db={db}&page=authorizeClient"
            f"&oauth_token={request_token} "
            "using a web browser to obtain a verification code."
        )
        verifier = input("Please enter verification code: ")
        service = self._get_service()
        resp = service.get_raw_access_token(
            request_token,
            request_secret,
            params={"oauth_verifier": verifier},
            headers={"User-Agent": "BIGSdb downloader"},
        )
        if resp.status_code == 200:
            token = resp.json()["oauth_token"]
            secret = resp.json()["oauth_token_secret"]
            print("Access Token:        " + token)
            print("Access Token Secret: " + secret + "\n")
            print(
                "This access token will not expire but may be revoked by the \n"
                f"user or the service provider. It will be saved to \n{file_path}."
            )
            config = configparser.ConfigParser(interpolation=None)
            if file_path.is_file():
                config.read(file_path)
            config[self.key_name] = {"token": token, "secret": secret}
            with open(file_path, "w", encoding="utf-8") as configfile:
                config.write(configfile)
            return (token, secret)

        sys.stderr.write("Failed to get new access token." + resp.json().get("message", ""))
        sys.exit(1)

    def _get_new_request_token(self):
        service = self._get_service()
        resp = service.get_raw_request_token(
            params={"oauth_callback": "oob"}, headers={"User-Agent": "BIGSdb downloader"}
        )
        if resp.status_code == 200:
            return (resp.json()["oauth_token"], resp.json()["oauth_token_secret"])
        sys.stderr.write("Failed to get new request token." + resp.json().get("message", ""))
        sys.exit(1)

    def _get_client_credentials(self):
        config = configparser.ConfigParser(interpolation=None)
        file_path = Path(f"{self.token_dir}/client_credentials")
        client_id = None
        if file_path.is_file():
            config.read(file_path)
            if config.has_section(self.key_name):
                client_id = config[self.key_name]["client_id"]
                client_secret = config[self.key_name]["client_secret"]
        if not client_id:
            if self.cron:
                sys.stderr.write(f"No client credentials saved for {self.key_name}.\n")
                sys.stderr.write("Run interactively to set.\n")
                sys.exit(1)
            client_id = input("Enter client id: ").strip()
            while len(client_id) != 24:
                print("Client ids are exactly 24 characters long.")
                client_id = input("Enter client id: ").strip()
            client_secret = input("Enter client secret: ").strip()
            while len(client_secret) != 42:
                print("Client secrets are exactly 42 characters long.")
                client_secret = input("Enter client secret: ").strip()
            config[self.key_name] = {"client_id": client_id, "client_secret": client_secret}
            with open(file_path, "w", encoding="utf-8") as configfile:
                config.write(configfile)
        return client_id, client_secret

    def _get_db_value(self):
        if self.db:
            return self.db
        if self.url:
            match = re.search(r"/db/([^/]+)", self.url)
            if match:
                return match.group(1)
        raise ValueError("No db value found: provide --db or include /db/<name> in --url")

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_json(json_string):
        try:
            json.loads(json_string)
            return True
        except ValueError:
            return False

    @staticmethod
    def _trim_url_args(url):
        if "?" not in url:
            return url, {}
        trimmed_url, param_string = url.split("?", 1)
        params = parse_qs(param_string)
        processed = {}
        for key, val in params.items():
            try:
                processed[key] = int(val[0])
            except ValueError:
                processed[key] = val[0]
        return trimmed_url, processed

    def _get_route(self, url, token, secret, output_file=None):
        (client_key, client_secret) = self._get_client_credentials()
        session = OAuth1Session(
            client_key, client_secret, access_token=token, access_token_secret=secret
        )
        trimmed_url, request_params = self._trim_url_args(url)
        if self.method == "GET":
            resp = session.get(
                trimmed_url,
                params=request_params,
                headers={"User-Agent": "BIGSdb downloader"},
            )
        else:
            resp = session.post(
                trimmed_url,
                params=request_params,
                data="{}",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "BIGSdb downloader",
                },
                header_auth=True,
            )

        out = output_file or self.output_file
        if resp.status_code in (200, 201):
            if out:
                try:
                    with open(out, "w", encoding="utf-8") as file_handle:
                        if re.search("json", resp.headers.get("content-type", ""), flags=0):
                            file_handle.write(json.dumps(resp.json()))
                        else:
                            file_handle.write(resp.text)
                except IOError as exc:
                    sys.stderr.write(f"Error writing to file: {exc}\n")
            else:
                if re.search("json", resp.headers.get("content-type", ""), flags=0):
                    print(json.dumps(resp.json()))
                else:
                    print(resp.text)
        elif resp.status_code == 400:
            sys.stderr.write("Bad request - " + resp.json().get("message", "") + "\n")
            sys.exit(1)
        elif resp.status_code == 401:
            msg = resp.json().get("message", "")
            if re.search("unauthorized", msg):
                sys.stderr.write("Access denied - client is unauthorized\n")
                sys.exit(1)
            sys.stderr.write(msg + "\n")
            sys.stderr.write("Invalid session token, requesting new one...\n")
            (token, secret) = self._get_new_session_token()
            self._get_route(url, token, secret, output_file=output_file)
        else:
            sys.stderr.write(f"Error: {resp.text}\n")
            sys.exit(1)

    def _download_scheme_alleles(self, scheme_url, token, secret, output_dir):
        with urllib.request.urlopen(scheme_url) as response:
            data = json.loads(response.read())
        for locus_url in data.get("loci", []):
            locus = os.path.basename(locus_url)
            out_file = os.path.join(output_dir, f"{locus}.fasta")
            if self.force or not os.path.isfile(out_file):
                self._get_route(f"{locus_url}/alleles_fasta", token, secret, output_file=out_file)
                logger.info("Downloaded locus: %s", locus)
