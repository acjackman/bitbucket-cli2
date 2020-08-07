import os
from typing import Optional

import keyring


class ProfileKeys:
    APP_NAME = "bitbucket-cli2"

    def __init__(self, profile_name: Optional[str] = None):
        self.profile_name = profile_name or "default"

    @classmethod
    def from_envrion(cls) -> "ProfileKeys":
        return ProfileKeys(os.environ.get("BB_PROFILE"))

    @property
    def _username_field(self) -> Optional[str]:
        return f"username-{self.profile_name}"

    @property
    def _password_field(self) -> Optional[str]:
        return f"password-{self.profile_name}"

    @property
    def username(self) -> Optional[str]:
        result: str = keyring.get_password(self.APP_NAME, self._username_field)
        return result or None

    @property
    def password(self) -> Optional[str]:
        result: str = keyring.get_password(self.APP_NAME, self._password_field)
        return result or None

    def set_username(self, value: str) -> None:
        keyring.get_password(self.APP_NAME, self._username_field, value)

    def set_password(self, value: str) -> None:
        keyring.get_password(self.APP_NAME, self._username_field, value)
