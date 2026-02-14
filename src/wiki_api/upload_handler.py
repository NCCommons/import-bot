"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import json
import logging
from typing import Any, BinaryIO, Dict, Optional, Union, cast

import mwclient
from mwclient.client import Site

from .api_errors import (
    FileExistError,
    UploadByUrlDisabledError,
    InsufficientPermission,
    DuplicateFileError,
)

logger = logging.getLogger(__name__)


class UploadHandler:
    """
    Handles file uploads to a MediaWiki site using mwclient.
    """

    def __init__(self, site: Site):
        """
        Initialize connection to MediaWiki site.

        Args:
            site: mwclient Site object representing the MediaWiki site to connect to
        """
        self.site = site

    def handle_api_result(self, info: dict, kwargs: dict) -> bool:
        """
        Handle the result of an API call.

        Args:
            info: API response information
            kwargs: Additional keyword arguments for context

        Returns:
            True if the API call was successful, False otherwise
        """
        if not info:
            logger.error("Empty API response")
            return False

        # Handle standard API error envelope
        if "error" in info:
            code = info["error"].get("code", "")
            err_info = info["error"].get("info", "")

            logger.error(f"API error: {info}")

            # {'error': {'code': 'copyuploaddisabled', 'info': 'Upload by URL disabled.', '*': ''}}
            if code == "copyuploaddisabled" or "upload by url disabled" in err_info.lower():
                raise UploadByUrlDisabledError()

            # Rate limit surface for caller
            if code in {"ratelimited", "throttled"} or "rate" in code:
                raise Exception("ratelimited: " + err_info)

            # Permission issues
            if code in {"permissiondenied", "badtoken", "mwoauth-invalid-authorization"}:
                raise InsufficientPermission()

            raise Exception(f"upload error: {code}: {err_info}")

        upload = info.get("upload", {})

        # Warnings handling
        warnings = upload.get("warnings", {})

        duplicate = warnings.get("duplicate", [""])[0].replace("_", " ")
        if duplicate:
            raise DuplicateFileError(kwargs.get("filename", ""), duplicate)

        if "exists" in warnings:
            raise FileExistError(kwargs.get("filename", ""))

        return True

    def mwclient_upload(
        self,
        file: Union[str, BinaryIO, None] = None,
        filename: Optional[str] = None,
        description: str = "",
        url: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to the site.
        """

        if filename is None:
            raise TypeError("filename must be specified")

        if comment is None:
            comment = description

        text = description

        predata = {
            "action": "upload",
            "format": "json",
            "filename": filename,
            "comment": comment,
            "text": text,
            "token": self.site.get_token("edit"),
        }
        if url:
            predata["url"] = url

        postdata = predata

        files = None

        if file is not None:
            if not hasattr(file, "read"):
                file = open(file, "rb")

            # Narrowing the type of file from Union[str, BinaryIO, None]
            # to BinaryIO, since we know it's not a str at this point.
            file = cast(BinaryIO, file)
            file.seek(0)

            # Workaround for https://github.com/mwclient/mwclient/issues/65
            # ----------------------------------------------------------------
            # Since the filename in Content-Disposition is not interpreted,
            # we can send some ascii-only dummy name rather than the real
            # filename, which might contain non-ascii.
            files = {"file": ("fake-filename", file)}

        data = self.site.raw_call("api", postdata, files)
        info = json.loads(data)

        if file is not None:
            file.close()

        if not info:
            return {"error": "Empty API response"}

        response = info

        if "for notice of API deprecations and breaking changes." in info.get("error", {}).get("*", ""):
            info["error"]["*"] = ""

        # Success
        if info.get("upload", {}).get("result") == "Success":
            return info

        if self.handle_api_result(info, kwargs=predata):
            response = info.get("upload", {})

        return response

    def upload(self, file, filename: str, description: str, comment: str, url: Optional[str] = None) -> dict:
        """
        Upload a file to the MediaWiki site.

        Args:
            file: File-like object to upload (or None if using URL upload)
            filename: Target filename on the wiki
            description: File description page content
            comment: Upload comment/summary
            url: Optional URL for direct upload (if supported)

        Returns:
            Dictionary with 'success' key indicating result and optional 'error' key for error details
        """
        filename = filename.removeprefix("File:")  # Ensure filename does not have 'File:' prefix

        try:
            logger.info(f"Uploading file: {filename}")
            _response = self.mwclient_upload(
                file=file,
                filename=filename,
                description=description,
                comment=comment,
                url=url,
            )
            logger.info(f"Upload successful: {filename}")
            return {"success": True}

        except DuplicateFileError as e:
            logger.warning(f"Duplicate file detected: {e.file_name} is a duplicate of {e.duplicate_name}")
            return {"success": False, "error": "duplicate", "duplicate_of": e.duplicate_name}

        except FileExistError as e:
            logger.warning(f"File already exists: {e.file_name}")
            return {"success": False, "error": "exists"}

        except InsufficientPermission:
            logger.error(f"Insufficient permissions to upload the file for user {self.site.username} on {self.site.host}")
            return {"success": False, "error": "permission_denied"}

        except UploadByUrlDisabledError:
            logger.warning(f"URL upload disabled in {self.site.host}")
            return {"success": False, "error": "url_disabled"}

        except mwclient.errors.APIError as e:
            error_msg = str(e)
            logger.error(f"Upload failed: {error_msg}")
            return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            return {"success": False, "error": str(e)}
