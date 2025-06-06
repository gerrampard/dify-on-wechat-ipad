import hashlib
import string
from random import choice
from typing import Union

import aiohttp
import qrcode

from .base import *
from .protect import protector
from ..errors import *


class LoginMixin(WechatAPIClientBase):
    async def is_running(self) -> bool:
        """检查WechatAPI是否在运行。

        Returns:
            bool: 如果WechatAPI正在运行返回True，否则返回False。
        """
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(f'http://{self.ip}:{self.port}{self.api_path_prefix}/IsRunning')
                return await response.text() == 'OK'
        except aiohttp.client_exceptions.ClientConnectorError:
            return False

    async def get_qr_code(self, device_name: str, device_id: str = "", proxy: Proxy = None, print_qr: bool = False) -> tuple[str, str]:
        """获取登录二维码。

        Args:
            device_name (str): 设备名称
            device_id (str, optional): 设备ID. Defaults to "".
            proxy (Proxy, optional): 代理信息. Defaults to None.
            print_qr (bool, optional): 是否在控制台打印二维码. Defaults to False.

        Returns:
            tuple[str, str]: 返回登录二维码的UUID和URL

        Raises:
            根据error_handler处理错误
        """
        async with aiohttp.ClientSession() as session:
            json_param = {'DeviceName': device_name, 'DeviceID': device_id}
            if proxy:
                json_param['ProxyInfo'] = {'ProxyIp': f'{proxy.ip}:{proxy.port}',
                                           'ProxyPassword': proxy.password,
                                           'ProxyUser': proxy.username}

            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/GetQR', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):

                if print_qr:
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(f'http://weixin.qq.com/x/{json_resp.get("Data").get("Uuid")}')
                    qr.make(fit=True)
                    qr.print_ascii()

                return json_resp.get("Data").get("Uuid"), json_resp.get("Data").get("QrUrl")
            else:
                # self.error_handler(json_resp)
                return "", ""

    async def check_login_uuid(self, uuid: str, device_id: str = "") -> tuple[bool, Union[dict, int]]:
        """检查登录的UUID状态。

        Args:
            uuid (str): 登录的UUID
            device_id (str, optional): 设备ID. Defaults to "".

        Returns:
            tuple[bool, Union[dict, int]]: 如果登录成功返回(True, 用户信息)，否则返回(False, 过期时间)

        Raises:
            根据error_handler处理错误
        """
        async with aiohttp.ClientSession() as session:
            json_param = {"uuid": uuid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/CheckQR', data=json_param)
            if response.content_type == 'application/json':
                json_resp = await response.json()
                if json_resp and json_resp.get("Success"):
                    if json_resp.get("Data").get("acctSectResp", ""):
                        self.wxid = json_resp.get("Data").get("acctSectResp").get("userName")
                        self.nickname = json_resp.get("Data").get("acctSectResp").get("nickName")
                        protector.update_login_status(device_id=device_id)
                        return True, json_resp.get("Data")
                    else:
                        return False, json_resp.get("Data").get("expiredTime")
                else:
                    return False,"错误"
            else:
                return False,"错误"

    async def log_out(self) -> bool:
        """登出当前账号。

        Returns:
            bool: 登出成功返回True，否则返回False

        Raises:
            UserLoggedOut: 如果未登录时调用
            根据error_handler处理错误
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/Logout', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            elif json_resp.get("Success"):
                return False
            else:
                self.error_handler(json_resp)

    async def awaken_login(self, wxid: str = "") -> str:
        """唤醒登录。

        Args:
            wxid (str, optional): 要唤醒的微信ID. Defaults to "".

        Returns:
            str: 返回新的登录UUID

        Raises:
            Exception: 如果未提供wxid且未登录
            LoginError: 如果无法获取UUID
            根据error_handler处理错误
        """
        if not wxid and not self.wxid:
            raise Exception("Please login using QRCode first")

        if not wxid and self.wxid:
            wxid = self.wxid

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/Awaken', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success") and json_resp.get("Data").get("QrCodeResponse").get("Uuid"):
                return json_resp.get("Data").get("QrCodeResponse").get("Uuid")
            elif not json_resp.get("Data").get("QrCodeResponse").get("Uuid"):
                # raise LoginError("Please login using QRCode first")
                return ""
            else:
                # self.error_handler(json_resp)
                return ""

    async def twice_login(self, wxid: str = "") -> str:
        """二次登录。

        Args:
            wxid (str, optional): 二次的微信ID. Defaults to "".

        Returns:
            str: 返回登录信息

        Raises:
            Exception: 如果未提供wxid且未登录
            LoginError: 如果无法获取UUID
            根据error_handler处理错误
        """
        if not wxid and not self.wxid:
            raise Exception("Please login using QRCode first")

        if not wxid and self.wxid:
            wxid = self.wxid

        async with aiohttp.ClientSession() as session:
            json_param = {"wxid": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/TwiceAutoAuth', data=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data")
            else:
                # self.error_handler(json_resp)
                return ""

    async def get_cached_info(self, wxid: str = "") -> dict:
        """获取登录缓存信息。

        Args:
            wxid (str, optional): 要查询的微信ID. Defaults to None.

        Returns:
            dict: 返回缓存信息，如果未提供wxid且未登录返回空字典
        """

        async with aiohttp.ClientSession() as session:
            json_param = {"wxid": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/GetCacheInfo', data=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data")
            else:
                return self.error_handler(json_resp)

    async def heartbeat(self) -> bool:
        """发送心跳包。

        Returns:
            bool: 成功返回True，否则返回False

        Raises:
            UserLoggedOut: 如果未登录时调用
            根据error_handler处理错误
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/Heartbeat', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                # self.error_handler(json_resp)
                return False

    async def start_auto_heartbeat(self) -> bool:
        """开始自动心跳。

        Returns:
            bool: 成功返回True，否则返回False

        Raises:
            UserLoggedOut: 如果未登录时调用
            根据error_handler处理错误
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/HeartBeat', data=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                # self.error_handler(json_resp)
                return False

    async def stop_auto_heartbeat(self) -> bool:
        """停止自动心跳。

        Returns:
            bool: 成功返回True，否则返回False

        Raises:
            UserLoggedOut: 如果未登录时调用
            根据error_handler处理错误
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/AutoHeartbeatStop', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def get_auto_heartbeat_status(self) -> bool:
        """获取自动心跳状态。

        Returns:
            bool: 如果正在运行返回True，否则返回False

        Raises:
            UserLoggedOut: 如果未登录时调用
            根据error_handler处理错误
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/AutoHeartbeatStatus', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("Running")
            else:
                return False

    async def update_device_token(self, wxid: str = "", device_id: str = "") -> bool:
        """刷新设备Token，延长session有效期。

        Args:
            wxid (str, optional): 要刷新的微信ID. Defaults to "".
            device_id (str, optional): 设备ID. Defaults to "".

        Returns:
            bool: 成功返回True，否则返回False

        Raises:
            Exception: 如果未提供wxid且未登录
            根据error_handler处理错误
        """
        if not wxid and not self.wxid:
            raise Exception("Please login first")

        if not wxid and self.wxid:
            wxid = self.wxid

        async with aiohttp.ClientSession() as session:
            json_param = {"wxid": wxid}
            if device_id:
                json_param["deviceId"] = device_id
            
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/UpdateDeviceToken', data=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                # self.error_handler(json_resp)
                return False

    async def refresh_token(self, wxid: str = "", device_id: str = "") -> bool:
        """刷新登录Token，延长session有效期。

        Args:
            wxid (str, optional): 要刷新的微信ID. Defaults to "".
            device_id (str, optional): 设备ID. Defaults to "".

        Returns:
            bool: 成功返回True，否则返回False

        Raises:
            Exception: 如果未提供wxid且未登录
            根据error_handler处理错误
        """
        if not wxid and not self.wxid:
            raise Exception("Please login first")

        if not wxid and self.wxid:
            wxid = self.wxid

        async with aiohttp.ClientSession() as session:
            json_param = {"wxid": wxid}
            if device_id:
                json_param["deviceId"] = device_id
            
            response = await session.post(f'http://{self.ip}:{self.port}{self.api_path_prefix}/Login/RefreshToken', data=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                # self.error_handler(json_resp)
                return False

    @staticmethod
    def create_device_name() -> str:
        """生成一个随机的设备名。

        Returns:
            str: 返回生成的设备名
        """
        first_names = [
            "Oliver", "Emma", "Liam", "Ava", "Noah", "Sophia", "Elijah", "Isabella",
            "James", "Mia", "William", "Amelia", "Benjamin", "Harper", "Lucas", "Evelyn",
            "Henry", "Abigail", "Alexander", "Ella", "Jackson", "Scarlett", "Sebastian",
            "Grace", "Aiden", "Chloe", "Matthew", "Zoey", "Samuel", "Lily", "David",
            "Aria", "Joseph", "Riley", "Carter", "Nora", "Owen", "Luna", "Daniel",
            "Sofia", "Gabriel", "Ellie", "Matthew", "Avery", "Isaac", "Mila", "Leo",
            "Julian", "Layla"
        ]

        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
            "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
            "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
            "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
            "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
            "Mitchell", "Carter", "Roberts", "Gomez", "Phillips", "Evans"
        ]

        return choice(first_names) + " " + choice(last_names) + "'s Pad"

    @staticmethod
    def create_device_id(s: str = "") -> str:
        """生成设备ID。

        Args:
            s (str, optional): 用于生成ID的字符串. Defaults to "".

        Returns:
            str: 返回生成的设备ID
        """
        if s == "" or s == "string":
            s = ''.join(choice(string.ascii_letters) for _ in range(15))
        md5_hash = hashlib.md5(s.encode()).hexdigest()
        return "49" + md5_hash[2:]
