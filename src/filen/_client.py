from filen.api.models.auth import NO_2FA_CODE_PLACEHOLDER, UserKeys
from filen.crypto import derive_master_key_and_hashed_password
from filen.repo import AsyncAuth, AsyncFilenClientRepo, AsyncUser, Auth, FilenClientRepo, User, async_repo, repo


class FilenClient(FilenClientRepo):
    """Filen client"""

    _auth: Auth = repo(Auth)
    user: User = repo(User)

    def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        return self._auth.login(email, password, two_factor_code)

    def logged_in(self) -> bool:
        return self._auth.logged_in()

    def update_context(self) -> bool:
        """Update the client context with user info"""

        if not self.logged_in():
            return False

        if not self._context.has_master_keys() and self._context.has_credentials():
            auth_info = self._auth.info(self._context.email)
            derived_info = derive_master_key_and_hashed_password(self._context.password, auth_info.salt)
            self._context.master_keys = [derived_info.master_key]

        user_info = self.user.info()
        master_keys = self.user.master_keys()
        key_pair = self.user.key_pair()

        self._context.email = user_info.email
        self._context.user_id = user_info.id
        self._context.base_folder_uuid = user_info.base_folder_uuid
        self._context.master_keys = master_keys
        self._context.public_key = key_pair.public_key
        self._context.private_key = key_pair.private_key

        return True


class AsyncFilenClient(AsyncFilenClientRepo):
    """Filen async client"""

    _auth: AsyncAuth = async_repo(AsyncAuth)
    user: AsyncUser = async_repo(AsyncUser)

    async def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        return await self._auth.login(email, password, two_factor_code)

    async def logged_in(self) -> bool:
        return await self._auth.logged_in()

    async def update_context(self) -> bool:
        if not await self.logged_in():
            return False

        if not self._context.has_master_keys() and self._context.has_credentials():
            auth_info = await self._auth.info(self._context.email)
            derived_info = await self._runner.run_sync(
                derive_master_key_and_hashed_password, self._context.password, auth_info.salt
            )
            self._context.master_keys = [derived_info.master_key]

        user_info = await self.user.info()
        master_keys = await self.user.master_keys()
        key_pair = await self.user.key_pair()

        self._context.email = user_info.email
        self._context.user_id = user_info.id
        self._context.base_folder_uuid = user_info.base_folder_uuid
        self._context.master_keys = master_keys
        self._context.public_key = key_pair.public_key
        self._context.private_key = key_pair.private_key

        return True
